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
session id: 019e1cce-cc51-77a0-90a7-76ec5559fcfc
--------
user
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

codex
I’ll verify the R3 claims directly from the repo: inspect the absorption diff, migration constraints, loader conflict handling, and the new replay test, then run the focused tests if the environment permits.
2026-05-12T15:29:51.528508Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git show --stat --oneline --decorate --no-renames 82617b9'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"UniqueConstraint|PrimaryKeyConstraint|Numeric\\(16, 6\\)|APPEND_ONLY|on_conflict_do_nothing|test_append_only_replay\" ." in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git show --stat --oneline --decorate --no-renames 82617b9' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git show --stat --oneline --decorate --no-renames 82617b9'` rejected: blocked by policy
 succeeded in 990ms:
.\AGENTS.md:20:2178 10:31a 🟣 Batch 09 APPEND_ONLY ACD Cycle Test Pattern (Authoritative for History Batches)
.\AGENTS.md:22:2181 " ✅ Batch 09 APPEND_ONLY History Pattern Committed to develop (B9.B C14)
.\AGENTS.md:50:2207 " ✅ Updated Migration Generator to Emit PrimaryKeyConstraint from natural_key Metadata
.\AGENTS.md:57:2214 " 🔵 Migration Regeneration Verified: 99 PrimaryKeyConstraints + 1 Numeric(16,6) Emitted
.\AGENTS.md:73:**Investigated**: Codex B9.B GATE-CLOSE R1 identified 2 HIGH blockers (missing loader path, missing PK constraints in migration) + 3 MEDIUM issues (scope mismatch, numeric precision, missing live-DB evidence). Root causes traced: load_fdb.py only had Phase 09 modes, 0009_fdb_tier_a.py lacked PrimaryKeyConstraint declarations, 99 UPSERT specs lacked natural_key metadata, UOM_CONVERSION_FACTOR precision mismatch (16,6 vs 16,5), and live testing deferred to Docker-up.
.\AGENTS.md:75:**Learned**: HIGH 1 blocker required a generic tier-driven loader (load_tier_group) that filters specs by loader_group and dispatches per delta_semantics (UPSERT_BY_NATURAL_KEY → ON CONFLICT DO UPDATE, APPEND_ONLY → plain INSERT, all-NK junctions → DO NOTHING). HIGH 2 required adding natural_key field to TableSpec + patching all 99 UPSERT specs + generator validation that raises ValueError if UPSERT without natural_key. MEDIUM 2 required a decimal_16_6 coercer as signaling mechanism for numeric precision override. Test failures in generator tests were fixture-level: test fixtures creating UPSERT specs without natural_key, fixed by updating _make_simple_tier_a_spec().
.\AGENTS.md:77:**Completed**: Created fdb_tier_loader.py (229 lines) with load_tier_group() dispatcher. Added natural_key field to TableSpec; programmatically patched 99 specs across 11 Tier A batches with correct natural_key tuples. Created decimal_16_6 coercer in fdb_adapter.py; updated generator's _sql_type_for_coercer() to recognize it. Enhanced generator to emit sa.PrimaryKeyConstraint() and validate natural_key presence (raises ValueError for incomplete UPSERT specs). Updated load_fdb.py to accept --mode fdb_tier_a and dispatch to new loader. Created 5 unit tests for tier loader (all passing). Fixed test fixture in test_gen_fdb_tier_migration.py by adding natural_key to _make_simple_tier_a_spec(). Regenerated 0009_fdb_tier_a.py migration: 1,432 lines with 99 PrimaryKeyConstraint entries + 1 Numeric(16,6) confirmed. Updated B9 status.md with R1 findings + absorption details. All changes committed in 18dcb20 (913 insertions, 18 files). Created B9.B GATE-CLOSE R2 prompt for verification dispatch.
.\AGENTS.md:79:**Next Steps**: Codex B9.B GATE-CLOSE R2 verification is now running in background (task b1m1ya3r9). R2 will inspect: (1) load_tier_group semantics for idempotency, (2) PrimaryKeyConstraint presence in migration, (3) numeric type emissions, (4) natural_key completeness across all UPSERT specs, (5) defensibility of MEDIUM 3 deferral. Awaiting R2 verdict (GO / GO-WITH-FIXES / NO-GO). Upon GO, B9.B officially closes and B9.C opens (72 Tier B tables absorbing 6 reclassifieds). Live-DB evidence deferred to Docker-up follow-on session per MEDIUM 3 scope.
.\data\reference\fdb\README.md:448:        UniqueConstraint(
.\data\reference\fdb\README.md:515:        UniqueConstraint("price_type_id", name="uq_fdb_price_type_id"),
.\data\reference\fdb\README.md:561:        UniqueConstraint(
.\docs\audit\wave-35-ifx-billing-audit.md:116:**Idempotency:** WEAK in billing.claim_records (UniqueConstraint
.\docs\audit\_scratch\05-security-data-compliance.md:126:`medical-claims`: `UniqueConstraint("tenant_id", "claim_number", "claim_line_number")` and additional NDC/quarter constraints.  
.\docs\audit\_scratch\05-security-data-compliance.md:127:`billing`: `UniqueConstraint("tenant_id", "auth_number")` on claims.
.\waves\B9\codex-adversarial-r2.md:284:| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness â€” mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
.\waves\B9\codex-adversarial-r2.md:347:| C1 | `TableSpec` registry expansion + new `DELTA_SEMANTICS` field (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD) | `modules/drug-database/src/.../fdb/specs.py`, unit tests |
.\waves\B9\codex-adversarial-r2.md:651:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) â€” ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-adversarial-r2.md:3794:          Postgres Ã¢â‚¬â€ pg_insert().on_conflict_do_nothing(constraint=
.\waves\B9\codex-adversarial-r2.md:3798:          SQLite   Ã¢â‚¬â€ sqlite_insert().on_conflict_do_nothing(index_elements=
.\waves\B9\codex-adversarial-r2.md:3842:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-adversarial-r2.md:3849:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
.\waves\B9\codex-adversarial-r2.md:3933:    UniqueConstraint,
.\waves\B9\codex-adversarial-r2.md:3969:        UniqueConstraint(
.\waves\B9\codex-adversarial-r2.md:4904:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-adversarial-r2.md:6010:38:| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness — mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
.\waves\B9\codex-adversarial-r2.md:6033:101:| C1 | `TableSpec` registry expansion + new `DELTA_SEMANTICS` field (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD) | `modules/drug-database/src/.../fdb/specs.py`, unit tests |
.\waves\B9\codex-adversarial-r2.md:6064:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-adversarial-r1.md:3056:          Postgres â€” pg_insert().on_conflict_do_nothing(constraint=
.\waves\B9\codex-adversarial-r1.md:3060:          SQLite   â€” sqlite_insert().on_conflict_do_nothing(index_elements=
.\waves\B9\codex-adversarial-r1.md:3104:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-adversarial-r1.md:3111:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
.\waves\B9\codex-adversarial-r1.md:3195:    UniqueConstraint,
.\waves\B9\codex-adversarial-r1.md:3231:        UniqueConstraint(
.\waves\B9\codex-adversarial-r1.md:4166:modules\drug-database\drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:22:  - APPEND_ONLY → plain INSERT (every row appends)
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:54:sa.PrimaryKeyConstraint('col_a', 'col_b', name='pk_<table>'),
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:59:- **99 PrimaryKeyConstraint entries** confirmed via grep
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:60:- **1 Numeric(16, 6)** confirmed (UOM_CONVERSION_FACTOR — see MEDIUM 2)
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:62:The 8 APPEND_ONLY history specs do not need natural_key — they have
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:75:`_sql_type_for_coercer` now maps it to `sa.Numeric(16, 6)`. `batch_10`
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:78:`Numeric(16, 6)` emission.
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:107:   `PrimaryKeyConstraint` in every CREATE TABLE block for UPSERT
.\waves\B9\codex-b9b-gate-close-r2-prompt.md:112:   `sa.Numeric(16, 6)` exactly once (UOM_CONVERSION_FACTOR), and
.\waves\B9\codex-b9b-gate-close-r2-result.md:35:  - APPEND_ONLY → plain INSERT (every row appends)
.\waves\B9\codex-b9b-gate-close-r2-result.md:67:sa.PrimaryKeyConstraint('col_a', 'col_b', name='pk_<table>'),
.\waves\B9\codex-b9b-gate-close-r2-result.md:72:- **99 PrimaryKeyConstraint entries** confirmed via grep
.\waves\B9\codex-b9b-gate-close-r2-result.md:73:- **1 Numeric(16, 6)** confirmed (UOM_CONVERSION_FACTOR — see MEDIUM 2)
.\waves\B9\codex-b9b-gate-close-r2-result.md:75:The 8 APPEND_ONLY history specs do not need natural_key — they have
.\waves\B9\codex-b9b-gate-close-r2-result.md:88:`_sql_type_for_coercer` now maps it to `sa.Numeric(16, 6)`. `batch_10`
.\waves\B9\codex-b9b-gate-close-r2-result.md:91:`Numeric(16, 6)` emission.
.\waves\B9\codex-b9b-gate-close-r2-result.md:120:   `PrimaryKeyConstraint` in every CREATE TABLE block for UPSERT
.\waves\B9\codex-b9b-gate-close-r2-result.md:125:   `sa.Numeric(16, 6)` exactly once (UOM_CONVERSION_FACTOR), and
.\waves\B9\codex-b9b-gate-close-r2-result.md:235:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r2-result.md:295:   - **APPEND_ONLY history** (batch_09): 2-5 columns;
.\waves\B9\codex-b9b-gate-close-r2-result.md:297:     tombstone append; contract template's APPEND_ONLY branch
.\waves\B9\codex-b9b-gate-close-r2-result.md:335:4. **APPEND_ONLY ACD test pattern** in batch_09. The contract
.\waves\B9\codex-b9b-gate-close-r2-result.md:336:   template's APPEND_ONLY branch asserts count >= 4 after A/C/D/re-A
.\waves\B9\codex-b9b-gate-close-r2-result.md:386:  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
.\waves\B9\codex-b9b-gate-close-r2-result.md:411:    DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:463:for all-NK junction tables, and plain INSERT for APPEND_ONLY.
.\waves\B9\codex-b9b-gate-close-r2-result.md:603:            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-b9b-gate-close-r2-result.md:630:                    stmt = stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r2-result.md:752:        return "sa.Numeric(16, 6)"
.\waves\B9\codex-b9b-gate-close-r2-result.md:783:    When `spec.natural_key` is non-empty, emits a PrimaryKeyConstraint
.\waves\B9\codex-b9b-gate-close-r2-result.md:794:            f'\n        sa.PrimaryKeyConstraint({pk_cols}, '
.\waves\B9\codex-b9b-gate-close-r2-result.md:1084:    Using this named coercer signals the generator to emit `Numeric(16, 6)`
.\waves\B9\codex-b9b-gate-close-r2-result.md:1174:      APPEND_ONLY                â€” immutable insert (pricing history; RNP3)
.\waves\B9\codex-b9b-gate-close-r2-result.md:1184:    APPEND_ONLY = "APPEND_ONLY"
.\waves\B9\codex-b9b-gate-close-r2-result.md:1226:                          Phase 09 behavior (treated as APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r2-result.md:1678:APPEND_ONLY) and replays cleanly (0 net new rows on second run).
.\waves\B9\codex-b9b-gate-close-r2-result.md:1751:_APPEND_ONLY_SPEC = TableSpec(
.\waves\B9\codex-b9b-gate-close-r2-result.md:1758:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:1901:The loader implements `ON CONFLICT` for UPSERT specs, but I’m checking one important edge case: Tier A includes APPEND_ONLY history specs, and the current loader intentionally plain-inserts them. That may conflict with the stated “re-run produces 0 net new rows” criterion unless the criterion is scoped to UPSERT specs only.
.\waves\B9\codex-b9b-gate-close-r2-result.md:1903:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"PrimaryKeyConstraint|Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|op.create_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:1905:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "natural_key=|delta_semantics=DeltaSemantics|APPEND_ONLY|UPSERT" modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:1920:50:        sa.PrimaryKeyConstraint('AHFS8', name="pk_rahfsd1_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1922:59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', name="pk_raplrt0_appl_relation_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1924:68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', name="pk_rappltd0_fda_appl_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1926:77:        sa.PrimaryKeyConstraint('ATC', name="pk_ratcd0_atc_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1928:86:        sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1930:95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', name="pk_rblasg0_substance_grp_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1932:104:        sa.PrimaryKeyConstraint('DCC', name="pk_rdccd0_drug_cat_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1934:113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', name="pk_retcctd0_etc_change_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1936:122:        sa.PrimaryKeyConstraint('GTC', name="pk_rgtcd0_gen_therap_class_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1938:131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', name="pk_rhicscd0_ing_stat_cd_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1940:140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', name="pk_rmedcd0_med_concept_typ_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1942:149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', name="pk_rmedmrd0_move_reason_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1944:159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', name="pk_raplt0_appl_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1946:169:        sa.PrimaryKeyConstraint('GCDF', name="pk_rdosed2_dose_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1948:179:        sa.PrimaryKeyConstraint('HIC1_SEQN', name="pk_rhic1d2_hic_organ_sys_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1950:190:        sa.PrimaryKeyConstraint('HIC2_SEQN', name="pk_rhic2d3_hic_rx_class_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1952:202:        sa.PrimaryKeyConstraint('HIC3_SEQN', name="pk_rhic3d3_hic_therap_class_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1954:212:        sa.PrimaryKeyConstraint('LBLRID', name="pk_rlblrid3_lblr_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1956:221:        sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1958:233:        sa.PrimaryKeyConstraint('MEDID', name="pk_rmedst0_medid_search_term"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1960:242:        sa.PrimaryKeyConstraint('SEARCH_TERM_TYPE_CD', name="pk_rmedstd0_search_term_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1962:251:        sa.PrimaryKeyConstraint('MED_REF_DESI2_IND', name="pk_rmide2d1_ref_desi2_ind_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1964:260:        sa.PrimaryKeyConstraint('MED_REF_DEA_CD', name="pk_rmidead1_ref_fed_dea_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1966:269:        sa.PrimaryKeyConstraint('MED_REF_DESI_IND', name="pk_rmidesd1_ref_desi_ind_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1968:279:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', name="pk_rmidfd1_dose_form"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1970:291:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', name="pk_rmidfid1_routed_dose_form_med"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1972:300:        sa.PrimaryKeyConstraint('MED_GCNSEQNO_ASSIGN_CD', name="pk_rmigcnd1_gcnseqno_assgn_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1974:309:        sa.PrimaryKeyConstraint('MED_REF_GEN_THERA_EQU_CD', name="pk_rmigecd1_ref_gen_therap_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1976:318:        sa.PrimaryKeyConstraint('MED_REF_GEN_DRUG_NAME_CD', name="pk_rmigncd1_ref_gen_name_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1978:327:        sa.PrimaryKeyConstraint('MED_REF_GEN_COMP_PRICE_CD', name="pk_rmigpcd1_ref_gen_prc_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1980:336:        sa.PrimaryKeyConstraint('MED_REF_GEN_SPREAD_CD', name="pk_rmigscd1_ref_gen_prc_sprd_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1982:345:        sa.PrimaryKeyConstraint('MED_REF_INNOV_IND', name="pk_rmiinnd1_ref_innov_ind_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1984:354:        sa.PrimaryKeyConstraint('MED_REF_FED_LEGEND_IND', name="pk_rmilgnd1_ref_fed_lgnd_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1986:363:        sa.PrimaryKeyConstraint('MED_REF_MULTI_SOURCE_CD', name="pk_rmimltd1_ref_multi_src_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1988:372:        sa.PrimaryKeyConstraint('MED_NAME_SOURCE_CD', name="pk_rminamd1_name_src_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1990:381:        sa.PrimaryKeyConstraint('MED_NAME_TYPE_CD', name="pk_rminmd1_med_name_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1992:393:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', name="pk_rmirmid1_routed_med"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1994:403:        sa.PrimaryKeyConstraint('MED_ROUTE_ID', name="pk_rmirtd1_route"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1996:412:        sa.PrimaryKeyConstraint('MED_STATUS_CD', name="pk_rmiscd1_status_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:1998:422:        sa.PrimaryKeyConstraint('OBC', name="pk_robcd0_obc_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2000:433:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiad0_attribute_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2002:444:        sa.PrimaryKeyConstraint('ATTRIBUTE_TYPE_CODE', name="pk_rpeiat0_attribute_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2004:454:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiav0_attribute_value_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2006:463:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeidfa0_dosage_form_attribute"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2008:475:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', name="pk_rpeidm0_dosage_form_mstr"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2010:484:        sa.PrimaryKeyConstraint('DOSAGE_FORM_TYPE_ID', name="pk_rpeidt0_dosage_form_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2012:493:        sa.PrimaryKeyConstraint('PATIENT_PARAM_REQ_CD', name="pk_rpeipp0_patient_param_req_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2014:502:        sa.PrimaryKeyConstraint('RT_LABELED_ID', name="pk_rpeirl0_rt_labeled_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2016:511:        sa.PrimaryKeyConstraint('STR_CONC_TYPE_ID', name="pk_rpeist0_str_conc_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2018:520:        sa.PrimaryKeyConstraint('UOM_TYPE_CD', name="pk_rpeiut0_uom_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2020:529:        sa.PrimaryKeyConstraint('CURRENCY_CD', name="pk_rprdcc0_currency_cd_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2022:540:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpad0_price_attr_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2024:549:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndctd0_ndc_attribute_typ_dsc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2026:559:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndcvd0_ndc_attribute_valu_dsc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2028:570:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_TYPE_CD', name="pk_rprdpat0_price_attr_type_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2030:580:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpav0_price_attr_value_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2032:592:        sa.PrimaryKeyConstraint('EXT_PRODUCT_CD_TYPE_ID', name="pk_rprdpcd0_ext_product_cd_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2034:603:        sa.PrimaryKeyConstraint('PACKAGE_TYPE_ID', name="pk_rprdpkd0_package_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2036:613:        sa.PrimaryKeyConstraint('FDB_PRODUCT_STATUS_CD', name="pk_rprdsd0_product_status_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2038:622:        sa.PrimaryKeyConstraint('PRICE_UOM_ID', name="pk_rprduom0_price_qty_uom"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2040:634:        sa.PrimaryKeyConstraint('GCRT', name="pk_rrouted3_route_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2042:646:        sa.PrimaryKeyConstraint('ROUTED_GEN_ID', name="pk_rrtgn0_routed_gen_mstr"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2044:655:        sa.PrimaryKeyConstraint('ROUTED_GEN_STATUS_CD', name="pk_rrtgnsd0_rtd_gen_status_dsc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2046:667:        sa.PrimaryKeyConstraint('STR60', name="pk_rstr1_strngth_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2048:676:        sa.PrimaryKeyConstraint('STRENGTH_STATUS_CODE', name="pk_rstrscd0_strength_status_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2050:685:        sa.PrimaryKeyConstraint('STRENGTH_TYP_CODE', name="pk_rstrtd0_strength_typ_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2052:696:        sa.PrimaryKeyConstraint('UOM_ID', name="pk_rstruom0_strength_uom"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2054:705:        sa.PrimaryKeyConstraint('TC', name="pk_rtcd0_std_therap_class_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2056:714:        sa.PrimaryKeyConstraint('TM_NAME_TYPE_ID', name="pk_rtmdt0_tm_name_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2058:723:        sa.PrimaryKeyConstraint('TM_GROUP_ID', name="pk_rtmgrpd1_tm_group_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2060:732:        sa.PrimaryKeyConstraint('TM_GNN_TYPE_ID', name="pk_rtmngt0_tm_gnn_type"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2062:741:        sa.PrimaryKeyConstraint('TM_SOURCE_ID', name="pk_rtmsrcd1_tm_source_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2064:752:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmdfid1_tm_routed_df_med"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2066:763:        sa.PrimaryKeyConstraint('MEDID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmmid1_tm_med"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2068:775:        sa.PrimaryKeyConstraint('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmngn0_tm_gnn"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2070:786:        sa.PrimaryKeyConstraint('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmnmid1_tm_med_name"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2072:797:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmrmid1_tm_routed_med"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2082:884:        sa.PrimaryKeyConstraint('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID', name="pk_retcsch0_etc_search"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2084:893:        sa.PrimaryKeyConstraint('ETC_ID', 'HIC3_SEQN', name="pk_retcxrf0_etc_hic3_etc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2086:902:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeial0_df_attribute_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2088:912:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'GCDF', name="pk_rpeigl0_gen_df_mstr_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2090:922:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID', name="pk_rpeiml0_med_df_mstr_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2092:932:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID', name="pk_rpeiol0_ovw_df_mstr_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2094:941:        sa.PrimaryKeyConstraint('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID', name="pk_rpeirer0_related_rt"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2096:950:        sa.PrimaryKeyConstraint('PARENT_RT_ID', 'CLINICAL_RT_ID', name="pk_rpeirh0_rt_hierarchy"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2098:959:        sa.Column('UOM_CONVERSION_FACTOR', sa.Numeric(16, 6), nullable=False),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2099:960:        sa.PrimaryKeyConstraint('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID', name="pk_rpeiuc0_uom_conversion"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2101:970:        sa.PrimaryKeyConstraint('DOSING_MODULE_UNIT_ABBREV', name="pk_runitsd0_units_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2103:979:        sa.PrimaryKeyConstraint('XRF_SOURCE_ID', name="pk_rxrnsrc0_source_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2105:991:        sa.PrimaryKeyConstraint('BLA_APPL_NBR', 'APPL_TYPE_ID', 'BIOLOGICS_SN', 'MULTI_INGREDIENT_SN', name="pk_rblahic0_ingredients"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2107:1002:        sa.PrimaryKeyConstraint('PROPRIETARY_NAME_ID', name="pk_rblapn0_proprietary_name"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2109:1013:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'GENERIC_MED_CONCEPT_ID', name="pk_rmedmgl0_med_generic_med_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2111:1025:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'HICL_SEQNO', name="pk_rmedmhl0_med_hiclseqno_link"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2113:1037:        sa.PrimaryKeyConstraint('FDB_PRODUCT_ID', 'EXT_PRODUCT_CD_TYPE_ID', 'EXT_PRODUCT_CD_START_DT', 'EXT_PRODUCT_CD', name="pk_rprdpc0_ext_product_cd"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2115:1047:        sa.PrimaryKeyConstraint('DAM_AGCSP', 'HIC_SEQN', name="pk_rxrfahx0_agcsp_hicseqn"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2117:1056:        sa.PrimaryKeyConstraint('DACN', 'DAM_AGCSP', name="pk_rxrfddx0_dacn_agcsp"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2119:1065:        sa.PrimaryKeyConstraint('GCDF', 'SCRIPT_QQ_ID', name="pk_rxrgdfq0_gcdf_script_qq"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2121:1074:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', 'SCRIPT_QQ_ID', name="pk_rxrmdfq0_meddosfm_script_qq"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2123:1086:        sa.PrimaryKeyConstraint('SCRIPT_QQ_ID', name="pk_rxrncqq0_qq_mstr"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2125:1095:        sa.PrimaryKeyConstraint('POEUNITCDE', 'SCRIPT_QQ_ID', name="pk_rxrpdfq0_poemdosfm_script_qq"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:2479:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -g "batch_*.py" "natural_key=|delta_semantics=DeltaSemantics|APPEND_ONLY|UPSERT" modules/drug-database/drug_database/services/fdb_tier_a' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:2481:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -o "PrimaryKeyConstraint" modules/drug-database/alembic/versions/0009_fdb_tier_a.py | Measure-Object | Select-Object -ExpandProperty Count' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:2625:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\waves\B9\codex-b9b-gate-close-r2-result.md:2627:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\waves\B9\codex-b9b-gate-close-r2-result.md:2628:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2629:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2630:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2631:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2632:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2633:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2634:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2635:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:2719:The migration has 99 primary-key constraints and exactly one `Numeric(16, 6)`. It has zero `Numeric(16, 5)` occurrences, so I’m checking whether Tier A actually has any remaining plain `Decimal` coercers; if not, that part of the requested check is vacuously satisfied rather than a regression.
.\waves\B9\codex-b9b-gate-close-r2-result.md:2729:append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
.\waves\B9\codex-b9b-gate-close-r2-result.md:2749:append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
.\waves\B9\codex-b9b-gate-close-r2-result.md:2771:append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
.\waves\B9\codex-b9b-gate-close-r2-result.md:2985:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/drug_database/services/fdb_tier_loader.py -Pattern "APPEND_ONLY|on_conflict_do_update|on_conflict_do_nothing|summary.inserted|unsupported_semantics|session.commit"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:2987:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/scripts/gen_fdb_tier_migration.py -Pattern \"natural_key|PrimaryKeyConstraint|Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|raises ValueError\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:2989:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Pattern \"APPEND_ONLY|Numeric\\(16, 6\\)|PrimaryKeyConstraint\" | Select-Object -First 20" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:2998:modules\drug-database\scripts\gen_fdb_tier_migration.py:85:        return "sa.Numeric(16, 6)"
.\waves\B9\codex-b9b-gate-close-r2-result.md:3000:PrimaryKeyConstraint
.\waves\B9\codex-b9b-gate-close-r2-result.md:3006:modules\drug-database\scripts\gen_fdb_tier_migration.py:127:            f'\n        sa.PrimaryKeyConstraint({pk_cols}, 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3023:APPEND_ONLY.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3025:DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-b9b-gate-close-r2-result.md:3030:stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r2-result.md:3041:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:50:        sa.PrimaryKeyConstraint('AHFS8', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3043:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3045:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3047:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:77:        sa.PrimaryKeyConstraint('ATC', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3050:sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:3051:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3053:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:104:        sa.PrimaryKeyConstraint('DCC', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3055:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3057:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:122:        sa.PrimaryKeyConstraint('GTC', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3059:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3061:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3063:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3065:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3067:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:169:        sa.PrimaryKeyConstraint('GCDF', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3069:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:179:        sa.PrimaryKeyConstraint('HIC1_SEQN', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3071:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:190:        sa.PrimaryKeyConstraint('HIC2_SEQN', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3073:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:202:        sa.PrimaryKeyConstraint('HIC3_SEQN', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3075:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:212:        sa.PrimaryKeyConstraint('LBLRID', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3078:sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
.\waves\B9\codex-b9b-gate-close-r2-result.md:3079:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:233:        sa.PrimaryKeyConstraint('MEDID', 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3104:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Pattern \"Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|APPEND_ONLY\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:3106:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py -Pattern "APPEND_ONLY|TableSpec|table_name"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:3108:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/tests/unit/test_fdb_tier_loader.py -Pattern "replays cleanly|APPEND_ONLY|on second run|plain|inserted"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r2-result.md:3112:delta=APPEND_ONLY record_counts_key=RETCHCH0
.\waves\B9\codex-b9b-gate-close-r2-result.md:3114:delta=APPEND_ONLY record_counts_key=RETCHLH0
.\waves\B9\codex-b9b-gate-close-r2-result.md:3116:delta=APPEND_ONLY record_counts_key=RETCNMH0
.\waves\B9\codex-b9b-gate-close-r2-result.md:3117:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:834:    # RHICRH0_ING_HIST — tier=A delta=APPEND_ONLY 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3120:delta=APPEND_ONLY record_counts_key=RMIDFRH1
.\waves\B9\codex-b9b-gate-close-r2-result.md:3121:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:852:    # RMINMRH1_MED_NAME_HIST — tier=A delta=APPEND_ONLY 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3123:modules\drug-database\alembic\versions\0009_fdb_tier_a.py:861:    # RMIRH1_MED_HIST — tier=A delta=APPEND_ONLY 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3126:delta=APPEND_ONLY record_counts_key=RMIRMRH1
.\waves\B9\codex-b9b-gate-close-r2-result.md:3128:sa.Numeric(16, 6), nullable=False),
.\waves\B9\codex-b9b-gate-close-r2-result.md:3134:modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3136:modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3143:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3148:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3153:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3157:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3162:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3166:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3170:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3174:delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3180:modules\drug-database\tests\unit\test_fdb_tier_loader.py:9:APPEND_ONLY) and replays cleanly (0 net new rows on second 
.\waves\B9\codex-b9b-gate-close-r2-result.md:3182:modules\drug-database\tests\unit\test_fdb_tier_loader.py:82:_APPEND_ONLY_SPEC = TableSpec(
.\waves\B9\codex-b9b-gate-close-r2-result.md:3183:modules\drug-database\tests\unit\test_fdb_tier_loader.py:89:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r2-result.md:3197:| HIGH | Generic Tier A loader idempotency | `load_tier_group` does not satisfy the stated full-mode gate criterion that `load_fdb.py --mode fdb_tier_a` re-run produces `0` net new rows. The UPSERT path is structurally correct, but the 8 APPEND_ONLY batch 09 history specs are included in Tier A and are loaded with plain `INSERT`, with no primary key or duplicate guard. Re-running the same drop will append duplicate rows for those tables. See [fdb_tier_loader.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:167>) and [batch_09.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1>). | Either narrow the gate criterion to UPSERT-only tables and explicitly exclude/defer APPEND_ONLY history from `fdb_tier_a`, or add an idempotency surface for APPEND_ONLY same-drop replay, such as a provenance/dedupe key, then add a real second-run loader test proving row counts do not grow on replay. |
.\waves\B9\codex-b9b-gate-close-r2-result.md:3203:- Generator now rejects UPSERT specs without `natural_key` and emits `PrimaryKeyConstraint` when present in [gen_fdb_tier_migration.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:256>).
.\waves\B9\codex-b9b-gate-close-r2-result.md:3204:- Migration has `99` `PrimaryKeyConstraint` entries.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3205:- Migration has exactly one `sa.Numeric(16, 6)`, on `UOM_CONVERSION_FACTOR`; I found zero `Numeric(16, 5)` entries in Tier A migration, so there do not appear to be other Tier A `Decimal` columns to preserve as `16,5`.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3207:- Live-DB evidence deferral is defensible as a separate Docker-up gate, but it does not cover the APPEND_ONLY replay gap above.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3209:So: not a fundamental NO-GO, but I would not mark B9.B officially closed until the APPEND_ONLY replay/idempotency framing is corrected.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3216:| HIGH | Generic Tier A loader idempotency | `load_tier_group` does not satisfy the stated full-mode gate criterion that `load_fdb.py --mode fdb_tier_a` re-run produces `0` net new rows. The UPSERT path is structurally correct, but the 8 APPEND_ONLY batch 09 history specs are included in Tier A and are loaded with plain `INSERT`, with no primary key or duplicate guard. Re-running the same drop will append duplicate rows for those tables. See [fdb_tier_loader.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:167>) and [batch_09.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1>). | Either narrow the gate criterion to UPSERT-only tables and explicitly exclude/defer APPEND_ONLY history from `fdb_tier_a`, or add an idempotency surface for APPEND_ONLY same-drop replay, such as a provenance/dedupe key, then add a real second-run loader test proving row counts do not grow on replay. |
.\waves\B9\codex-b9b-gate-close-r2-result.md:3222:- Generator now rejects UPSERT specs without `natural_key` and emits `PrimaryKeyConstraint` when present in [gen_fdb_tier_migration.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:256>).
.\waves\B9\codex-b9b-gate-close-r2-result.md:3223:- Migration has `99` `PrimaryKeyConstraint` entries.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3224:- Migration has exactly one `sa.Numeric(16, 6)`, on `UOM_CONVERSION_FACTOR`; I found zero `Numeric(16, 5)` entries in Tier A migration, so there do not appear to be other Tier A `Decimal` columns to preserve as `16,5`.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3226:- Live-DB evidence deferral is defensible as a separate Docker-up gate, but it does not cover the APPEND_ONLY replay gap above.
.\waves\B9\codex-b9b-gate-close-r2-result.md:3228:So: not a fundamental NO-GO, but I would not mark B9.B officially closed until the APPEND_ONLY replay/idempotency framing is corrected.
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:6:**R2 result:** GO-WITH-FIXES (1 HIGH residual on APPEND_ONLY replay)
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:12:### HIGH (R2 residual) — APPEND_ONLY history replay idempotency
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:14:R2 flagged that the 8 batch_09 APPEND_ONLY specs had no PK/unique
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:18:1. **All 8 APPEND_ONLY specs gained `natural_key=`** covering their
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:28:     → `sa.PrimaryKeyConstraint(*natural_key, name="pk_<table>")`
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:29:   - `APPEND_ONLY`
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:30:     → `sa.UniqueConstraint(*natural_key, name="uq_<table>")`
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:36:3. **Loader's APPEND_ONLY path** now branches on `spec.natural_key`:
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:44:`tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate`:
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:46:- Builds a SQLite table with `UniqueConstraint` over `(repl_id,
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:58:PrimaryKeyConstraint: 99    (every UPSERT spec has a PK target)
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:59:UniqueConstraint:       8   (every APPEND_ONLY spec has a UNIQUE target)
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:60:Numeric(16, 6):         1   (UOM_CONVERSION_FACTOR — R1 MEDIUM 2 unchanged)
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:81:   - `0009_fdb_tier_a.py` emits exactly 8 `UniqueConstraint` (for
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:83:   - Loader's APPEND_ONLY path uses `on_conflict_do_nothing` when
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:90:   - PrimaryKeyConstraint (99 UPSERT specs), or
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:91:   - UniqueConstraint (8 APPEND_ONLY specs).
.\waves\B9\codex-b9b-gate-close-r3-prompt.md:95:   raise (as enforced in R1). APPEND_ONLY without natural_key now
.\waves\B9\codex-b9b-gate-close-r1-result.md:51:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-result.md:111:   - **APPEND_ONLY history** (batch_09): 2-5 columns;
.\waves\B9\codex-b9b-gate-close-r1-result.md:113:     tombstone append; contract template's APPEND_ONLY branch
.\waves\B9\codex-b9b-gate-close-r1-result.md:151:4. **APPEND_ONLY ACD test pattern** in batch_09. The contract
.\waves\B9\codex-b9b-gate-close-r1-result.md:152:   template's APPEND_ONLY branch asserts count >= 4 after A/C/D/re-A
.\waves\B9\codex-b9b-gate-close-r1-result.md:202:  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
.\waves\B9\codex-b9b-gate-close-r1-result.md:227:    DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:846:a4ea4db B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-result.md:868:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:874:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
.\waves\B9\codex-b9b-gate-close-r1-result.md:877:2026-05-12T14:54:03.000553Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
.\waves\B9\codex-b9b-gate-close-r1-result.md:996:  {UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY},
.\waves\B9\codex-b9b-gate-close-r1-result.md:1304:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|create_index|unique=True\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py modules/drug-database/alembic/versions/0008_fdb_pricing.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:1306:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RPEIUC0_UOM_CONVERSION|UOM_CONVERSION_FACTOR|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0|APPEND_ONLY|_parse_fdb_date|Decimal" modules/drug-database/drug_database/services/fdb_tier_a modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:1320:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:1321:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\waves\B9\codex-b9b-gate-close-r1-result.md:1325:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1327:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1329:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1331:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1333:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1335:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1337:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1339:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1369:modules/drug-database/alembic/versions/0008_fdb_pricing.py:119:        sa.UniqueConstraint(
.\waves\B9\codex-b9b-gate-close-r1-result.md:1385:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:1386:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\waves\B9\codex-b9b-gate-close-r1-result.md:1390:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1392:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1394:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1396:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1398:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1400:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1402:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1404:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1436:modules/drug-database/tests/unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
.\waves\B9\codex-b9b-gate-close-r1-result.md:1462:modules/drug-database/tests/unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1469:modules/drug-database/tests/unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1483:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:72:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:1492:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:110:# APPEND_ONLY — every operation appends a row (no conflict resolution)
.\waves\B9\codex-b9b-gate-close-r1-result.md:1494:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1524:modules/drug-database/tests/unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1526:modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:412:def test_replay_uses_on_conflict_do_nothing(initial_drop, db_session):
.\waves\B9\codex-b9b-gate-close-r1-result.md:1536:modules/drug-database/drug_database/services\fdb_pricing_ingester.py:383:          Postgres — pg_insert().on_conflict_do_nothing(constraint=
.\waves\B9\codex-b9b-gate-close-r1-result.md:1537:modules/drug-database/drug_database/services\fdb_pricing_ingester.py:387:          SQLite   — sqlite_insert().on_conflict_do_nothing(index_elements=
.\waves\B9\codex-b9b-gate-close-r1-result.md:1539:modules/drug-database/drug_database/services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-b9b-gate-close-r1-result.md:1541:modules/drug-database/drug_database/services\fdb_pricing_ingester.py:438:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
.\waves\B9\codex-b9b-gate-close-r1-result.md:1795:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\waves\B9\codex-b9b-gate-close-r1-result.md:1805:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:1807:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1808:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1809:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1810:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1811:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1812:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1813:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1814:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:1816:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
.\waves\B9\codex-b9b-gate-close-r1-result.md:1828:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
.\waves\B9\codex-b9b-gate-close-r1-result.md:1842:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:1887:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "CONTRACT_TESTED_SPECS|BATCH_TESTED_NAMES|assert_delta_semantics_acd_cycle|if not non_nk_cols|count >= 4|APPEND_ONLY" modules/drug-database/tests/unit' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:2066:      APPEND_ONLY                â€” immutable insert (pricing history; RNP3)
.\waves\B9\codex-b9b-gate-close-r1-result.md:2076:    APPEND_ONLY = "APPEND_ONLY"
.\waves\B9\codex-b9b-gate-close-r1-result.md:2118:                          Phase 09 behavior (treated as APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:2407:modules/drug-database/tests/unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
.\waves\B9\codex-b9b-gate-close-r1-result.md:2412:modules/drug-database/tests/unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:2415:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:9:  * APPEND_ONLY history table                  → PASS (row count grows)
.\waves\B9\codex-b9b-gate-close-r1-result.md:2419:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:110:# APPEND_ONLY — every operation appends a row (no conflict resolution)
.\waves\B9\codex-b9b-gate-close-r1-result.md:2420:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:2425:modules/drug-database/tests/unit\test_fdb_contract_coverage.py:9:  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
.\waves\B9\codex-b9b-gate-close-r1-result.md:2429:modules/drug-database/tests/unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:2444:modules/drug-database/tests/unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:2471:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:1:"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).
.\waves\B9\codex-b9b-gate-close-r1-result.md:2472:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:3:batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
.\waves\B9\codex-b9b-gate-close-r1-result.md:2473:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:6:and the contract template's APPEND_ONLY branch asserts row-count
.\waves\B9\codex-b9b-gate-close-r1-result.md:2476:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:67:# APPEND_ONLY ACD cycle
.\waves\B9\codex-b9b-gate-close-r1-result.md:2477:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:78:    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.
.\waves\B9\codex-b9b-gate-close-r1-result.md:2478:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:80:    APPEND_ONLY semantics: every transaction grows the row count.
.\waves\B9\codex-b9b-gate-close-r1-result.md:2479:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\waves\B9\codex-b9b-gate-close-r1-result.md:2480:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:86:        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
.\waves\B9\codex-b9b-gate-close-r1-result.md:2481:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:90:    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
.\waves\B9\codex-b9b-gate-close-r1-result.md:2483:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:141:    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
.\waves\B9\codex-b9b-gate-close-r1-result.md:2484:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:2777:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|loader_group|REGISTERED_SPECS|load_fdb|DeltaSemantics|on_conflict_do_update|on_conflict_do_nothing" scripts modules/drug-database/drug_database modules/drug-database/tests -g "*.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:2831:waves/B9\codex-b9b-gate-close-r1-prompt.md:38:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-result.md:3222:waves/B9\codex-adversarial-r2.md:651:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) â€” ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-b9b-gate-close-r1-result.md:3503:waves/B9\codex-adversarial-r2.md:6064:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-b9b-gate-close-r1-result.md:3615:waves/B9\codex-b9b-gate-close-r1-result.md:51:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-result.md:3682:waves/B9\codex-b9b-gate-close-r1-result.md:846:a4ea4db B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-result.md:3696:waves/B9\codex-b9b-gate-close-r1-result.md:868:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:3698:waves/B9\codex-b9b-gate-close-r1-result.md:874:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
.\waves\B9\codex-b9b-gate-close-r1-result.md:3699:waves/B9\codex-b9b-gate-close-r1-result.md:877:2026-05-12T14:54:03.000553Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
.\waves\B9\codex-b9b-gate-close-r1-result.md:3714:waves/B9\codex-b9b-gate-close-r1-result.md:1304:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|create_index|unique=True\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py modules/drug-database/alembic/versions/0008_fdb_pricing.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:3715:waves/B9\codex-b9b-gate-close-r1-result.md:1306:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RPEIUC0_UOM_CONVERSION|UOM_CONVERSION_FACTOR|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0|APPEND_ONLY|_parse_fdb_date|Decimal" modules/drug-database/drug_database/services/fdb_tier_a modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:3725:waves/B9\codex-b9b-gate-close-r1-result.md:1320:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:3726:waves/B9\codex-b9b-gate-close-r1-result.md:1321:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\waves\B9\codex-b9b-gate-close-r1-result.md:3730:waves/B9\codex-b9b-gate-close-r1-result.md:1325:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3732:waves/B9\codex-b9b-gate-close-r1-result.md:1327:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3734:waves/B9\codex-b9b-gate-close-r1-result.md:1329:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3736:waves/B9\codex-b9b-gate-close-r1-result.md:1331:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3738:waves/B9\codex-b9b-gate-close-r1-result.md:1333:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3740:waves/B9\codex-b9b-gate-close-r1-result.md:1335:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3742:waves/B9\codex-b9b-gate-close-r1-result.md:1337:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3744:waves/B9\codex-b9b-gate-close-r1-result.md:1339:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3779:waves/B9\codex-b9b-gate-close-r1-result.md:1385:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:3780:waves/B9\codex-b9b-gate-close-r1-result.md:1386:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\waves\B9\codex-b9b-gate-close-r1-result.md:3784:waves/B9\codex-b9b-gate-close-r1-result.md:1390:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3786:waves/B9\codex-b9b-gate-close-r1-result.md:1392:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3788:waves/B9\codex-b9b-gate-close-r1-result.md:1394:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3790:waves/B9\codex-b9b-gate-close-r1-result.md:1396:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3792:waves/B9\codex-b9b-gate-close-r1-result.md:1398:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3794:waves/B9\codex-b9b-gate-close-r1-result.md:1400:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3796:waves/B9\codex-b9b-gate-close-r1-result.md:1402:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:3798:waves/B9\codex-b9b-gate-close-r1-result.md:1404:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4037:waves/B9\codex-b9b-gate-close-r1-result.md:1795:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\waves\B9\codex-b9b-gate-close-r1-result.md:4047:waves/B9\codex-b9b-gate-close-r1-result.md:1805:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:4049:waves/B9\codex-b9b-gate-close-r1-result.md:1807:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4050:waves/B9\codex-b9b-gate-close-r1-result.md:1808:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4051:waves/B9\codex-b9b-gate-close-r1-result.md:1809:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4052:waves/B9\codex-b9b-gate-close-r1-result.md:1810:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4053:waves/B9\codex-b9b-gate-close-r1-result.md:1811:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4054:waves/B9\codex-b9b-gate-close-r1-result.md:1812:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4055:waves/B9\codex-b9b-gate-close-r1-result.md:1813:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4056:waves/B9\codex-b9b-gate-close-r1-result.md:1814:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:4058:waves/B9\codex-b9b-gate-close-r1-result.md:1816:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
.\waves\B9\codex-b9b-gate-close-r1-result.md:4070:waves/B9\codex-b9b-gate-close-r1-result.md:1828:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
.\waves\B9\codex-b9b-gate-close-r1-result.md:4084:waves/B9\codex-b9b-gate-close-r1-result.md:1842:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:4131:waves/B9\codex-b9b-gate-close-r1-result.md:2415:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:9:  * APPEND_ONLY history table                  → PASS (row count grows)
.\waves\B9\codex-b9b-gate-close-r1-result.md:4159:waves/B9\codex-b9b-gate-close-r1-result.md:2471:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:1:"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).
.\waves\B9\codex-b9b-gate-close-r1-result.md:4160:waves/B9\codex-b9b-gate-close-r1-result.md:2472:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:3:batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
.\waves\B9\codex-b9b-gate-close-r1-result.md:4161:waves/B9\codex-b9b-gate-close-r1-result.md:2473:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:6:and the contract template's APPEND_ONLY branch asserts row-count
.\waves\B9\codex-b9b-gate-close-r1-result.md:4164:waves/B9\codex-b9b-gate-close-r1-result.md:2476:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:67:# APPEND_ONLY ACD cycle
.\waves\B9\codex-b9b-gate-close-r1-result.md:4165:waves/B9\codex-b9b-gate-close-r1-result.md:2477:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:78:    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.
.\waves\B9\codex-b9b-gate-close-r1-result.md:4166:waves/B9\codex-b9b-gate-close-r1-result.md:2478:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:80:    APPEND_ONLY semantics: every transaction grows the row count.
.\waves\B9\codex-b9b-gate-close-r1-result.md:4167:waves/B9\codex-b9b-gate-close-r1-result.md:2479:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\waves\B9\codex-b9b-gate-close-r1-result.md:4168:waves/B9\codex-b9b-gate-close-r1-result.md:2480:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:86:        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
.\waves\B9\codex-b9b-gate-close-r1-result.md:4169:waves/B9\codex-b9b-gate-close-r1-result.md:2481:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:90:    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
.\waves\B9\codex-b9b-gate-close-r1-result.md:4171:waves/B9\codex-b9b-gate-close-r1-result.md:2483:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:141:    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
.\waves\B9\codex-b9b-gate-close-r1-result.md:4172:waves/B9\codex-b9b-gate-close-r1-result.md:2484:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:4190:waves/B9\codex-b9b-gate-close-r1-result.md:2777:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|loader_group|REGISTERED_SPECS|load_fdb|DeltaSemantics|on_conflict_do_update|on_conflict_do_nothing" scripts modules/drug-database/drug_database modules/drug-database/tests -g "*.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:4333:waves/B9\plan.md:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-b9b-gate-close-r1-result.md:4432:waves/B9\codex-gate-close-r1-result.md:3205:  * APPEND_ONLY history table                  â†’ PASS (row count grows)
.\waves\B9\codex-b9b-gate-close-r1-result.md:5360:modules/drug-database/tests\_fdb_delta_semantics.py:165:                            stmt = stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:5361:modules/drug-database/tests\_fdb_delta_semantics.py:170:                        stmt = stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:5365:modules/drug-database/tests\_fdb_contract.py:559:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-b9b-gate-close-r1-result.md:5371:modules/drug-database/tests\unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
.\waves\B9\codex-b9b-gate-close-r1-result.md:5386:modules/drug-database/tests\unit\test_fdb_delta_semantics.py:72:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:5388:modules/drug-database/tests\unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5397:modules/drug-database/tests\unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5405:modules/drug-database/tests\unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5414:modules/drug-database/tests\unit\test_fdb_pricing_ingester.py:412:def test_replay_uses_on_conflict_do_nothing(initial_drop, db_session):
.\waves\B9\codex-b9b-gate-close-r1-result.md:5418:modules/drug-database/tests\unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5512:modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\waves\B9\codex-b9b-gate-close-r1-result.md:5515:modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\waves\B9\codex-b9b-gate-close-r1-result.md:5516:modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
.\waves\B9\codex-b9b-gate-close-r1-result.md:5520:modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
.\waves\B9\codex-b9b-gate-close-r1-result.md:5561:modules/drug-database/drug_database\services\fdb_pricing_ingester.py:383:          Postgres — pg_insert().on_conflict_do_nothing(constraint=
.\waves\B9\codex-b9b-gate-close-r1-result.md:5562:modules/drug-database/drug_database\services\fdb_pricing_ingester.py:387:          SQLite   — sqlite_insert().on_conflict_do_nothing(index_elements=
.\waves\B9\codex-b9b-gate-close-r1-result.md:5563:modules/drug-database/drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\waves\B9\codex-b9b-gate-close-r1-result.md:5564:modules/drug-database/drug_database\services\fdb_pricing_ingester.py:438:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
.\waves\B9\codex-b9b-gate-close-r1-result.md:5732:modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
.\waves\B9\codex-b9b-gate-close-r1-result.md:5758:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5760:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5762:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5764:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5766:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5768:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5770:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:5772:modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-b9b-gate-close-r1-result.md:6201:        Skip â€” Phase 09 backward-compat (treated as APPEND_ONLY by
.\waves\B9\codex-b9b-gate-close-r1-result.md:6227:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-b9b-gate-close-r1-result.md:6292:                    # Keeps the count growth invariant of APPEND_ONLY.
.\waves\B9\codex-b9b-gate-close-r1-result.md:6325:                            stmt = stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:6330:                        stmt = stmt.on_conflict_do_nothing(
.\waves\B9\codex-b9b-gate-close-r1-result.md:6427:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.Column|sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|sa\\.Numeric|rpeiuc0_uom_conversion|UOM_CONVERSION_FACTOR|GRANT SELECT\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-b9b-gate-close-r1-result.md:6795:waves/B9/plan.md:38:| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness — mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6847:waves/B9/plan.md:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6870:| HIGH | Migration / delta semantics | [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:48) creates columns but no PK/unique constraints. `rg` found no `PrimaryKeyConstraint`, `UniqueConstraint`, `primary_key=True`, or unique indexes in the migration. Without a DB uniqueness surface, `UPSERT_BY_NATURAL_KEY` is not enforceable in Postgres. | Add explicit natural-key metadata, emit matching PK/unique constraints or unique indexes, and add generator tests that fail if checkable specs lack DB conflict targets. |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6872:| MEDIUM | Numeric precision | `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR` is described as `NUMERIC(16,6)`, but the migration emits `sa.Numeric(16, 5)` at [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:874). This comes from the generator’s global Decimal mapping. | Add per-column precision metadata or a special coercer mapping and regenerate this column as `sa.Numeric(16, 6)`. |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6877:The APPEND_ONLY A/C/D/re-A test shape is directionally correct: a collapsing UPSERT path should fail the row-growth assertions. The all-natural-key junction-table handling is acceptable as an interim pattern, but it should be named separately from mutable `UPSERT_BY_NATURAL_KEY` so future reviewers do not assume the C-step validates an update.
.\waves\B9\codex-b9b-gate-close-r1-result.md:6887:| HIGH | Migration / delta semantics | [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:48) creates columns but no PK/unique constraints. `rg` found no `PrimaryKeyConstraint`, `UniqueConstraint`, `primary_key=True`, or unique indexes in the migration. Without a DB uniqueness surface, `UPSERT_BY_NATURAL_KEY` is not enforceable in Postgres. | Add explicit natural-key metadata, emit matching PK/unique constraints or unique indexes, and add generator tests that fail if checkable specs lack DB conflict targets. |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6889:| MEDIUM | Numeric precision | `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR` is described as `NUMERIC(16,6)`, but the migration emits `sa.Numeric(16, 5)` at [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:874). This comes from the generator’s global Decimal mapping. | Add per-column precision metadata or a special coercer mapping and regenerate this column as `sa.Numeric(16, 6)`. |
.\waves\B9\codex-b9b-gate-close-r1-result.md:6894:The APPEND_ONLY A/C/D/re-A test shape is directionally correct: a collapsing UPSERT path should fail the row-growth assertions. The all-natural-key junction-table handling is acceptable as an interim pattern, but it should be named separately from mutable `UPSERT_BY_NATURAL_KEY` so future reviewers do not assume the C-step validates an update.
.\waves\B9\codex-b9b-gate-close-r1-prompt.md:38:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
.\waves\B9\codex-b9b-gate-close-r1-prompt.md:98:   - **APPEND_ONLY history** (batch_09): 2-5 columns;
.\waves\B9\codex-b9b-gate-close-r1-prompt.md:100:     tombstone append; contract template's APPEND_ONLY branch
.\waves\B9\codex-b9b-gate-close-r1-prompt.md:138:4. **APPEND_ONLY ACD test pattern** in batch_09. The contract
.\waves\B9\codex-b9b-gate-close-r1-prompt.md:139:   template's APPEND_ONLY branch asserts count >= 4 after A/C/D/re-A
.\waves\B9\status.md:74:{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
.\waves\B9\status.md:148:| HIGH 2 | Migration `0009_fdb_tier_a.py` had no PK constraints — `ON CONFLICT` would fail at runtime | Added `natural_key: tuple[str, ...]` field to TableSpec; patched all 99 UPSERT specs across 11 batches; generator now emits `sa.PrimaryKeyConstraint(...)` per spec; generator validates natural_key presence for UPSERT semantics (raises ValueError otherwise) |
.\waves\B9\status.md:150:| MEDIUM 2 | `UOM_CONVERSION_FACTOR` was NUMERIC(16,6) emitted as Numeric(16,5) | New `decimal_16_6` coercer in `fdb_adapter.py`; generator maps it to `sa.Numeric(16, 6)`; batch_10 spec swapped to use it |
.\waves\B9\status.md:153:**Regenerated migration:** 1,432 lines (was 1,220); 99 `PrimaryKeyConstraint` + 1 `Numeric(16, 6)` confirmed via grep.
.\waves\B9\status.md:168:APPEND_ONLY history specs in batch_09 had no PK/unique constraint —
.\waves\B9\status.md:176:| HIGH | All 8 batch_09 APPEND_ONLY specs gained `natural_key=` covering their non-nullable columns (the immutable identifying tuple). Generator now emits `sa.UniqueConstraint` (not PK) for APPEND_ONLY specs with natural_key — history rows can repeat the same logical fact via DO NOTHING dedupe. Loader's APPEND_ONLY path applies `INSERT ... ON CONFLICT (natural_key) DO NOTHING` when natural_key is set, falling back to plain INSERT for legacy specs without it. |
.\waves\B9\status.md:178:**Regenerated migration:** 99 PrimaryKeyConstraint + **8 UniqueConstraint** + 1 Numeric(16,6). Every Tier A table now has a uniqueness surface.
.\waves\B9\status.md:180:**New replay-idempotency test** (`test_append_only_replay_with_natural_key_does_not_duplicate`): constructs SQLite table with UNIQUE index over natural_key, loads twice, asserts row count unchanged after second load. Green.
.\waves\B9\plan.md:38:| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness — mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
.\waves\B9\plan.md:101:| C1 | `TableSpec` registry expansion + new `DELTA_SEMANTICS` field (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD) | `modules/drug-database/src/.../fdb/specs.py`, unit tests |
.\waves\B9\plan.md:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
.\waves\B9\codex-plan-consult-r1.md:3647:modules\plan-design\src\models\tables.py:173:        UniqueConstraint("tenant_id", "code", name="uq_pricing_models_tenant_code"),
.\waves\B9\codex-gate-close-r1-result.md:110:   (`test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing`).
.\waves\B9\codex-gate-close-r1-result.md:1066:                                    APPEND_ONLY take the replay-safety
.\waves\B9\codex-gate-close-r1-result.md:1456:      APPEND_ONLY:
.\waves\B9\codex-gate-close-r1-result.md:1478:        Skip â€” Phase 09 backward-compat (treated as APPEND_ONLY by
.\waves\B9\codex-gate-close-r1-result.md:1504:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-gate-close-r1-result.md:3150:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r1-result.md:3205:  * APPEND_ONLY history table                  â†’ PASS (row count grows)
.\waves\B9\codex-gate-close-r1-result.md:3268:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
.\waves\B9\codex-gate-close-r1-result.md:3306:# APPEND_ONLY â€” every operation appends a row (no conflict resolution)
.\waves\B9\codex-gate-close-r1-result.md:3318:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r1-result.md:3547:178:      APPEND_ONLY                — immutable insert (pricing history; RNP3)
.\waves\B9\codex-gate-close-r1-result.md:3589:230-                          Phase 09 behavior (treated as APPEND_ONLY
.\waves\B9\codex-gate-close-r1-result.md:3712:47-    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r1-result.md:4361:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r3-result.md:819:{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
.\waves\B9\codex-gate-close-r3-result.md:2638:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r3-result.md:2788:                                    APPEND_ONLY take the replay-safety
.\waves\B9\codex-gate-close-r3-result.md:3245:      APPEND_ONLY:
.\waves\B9\codex-gate-close-r3-result.md:3267:        Skip Ã¢â‚¬â€ Phase 09 backward-compat (treated as APPEND_ONLY by
.\waves\B9\codex-gate-close-r3-result.md:3293:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-gate-close-r3-result.md:3451:{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
.\waves\B9\codex-gate-close-r1-prompt.md:97:   (`test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing`).
.\waves\B9\codex-b9b-gate-close-r3-result.md:19:**R2 result:** GO-WITH-FIXES (1 HIGH residual on APPEND_ONLY replay)
.\waves\B9\codex-b9b-gate-close-r3-result.md:25:### HIGH (R2 residual) — APPEND_ONLY history replay idempotency
.\waves\B9\codex-b9b-gate-close-r3-result.md:27:R2 flagged that the 8 batch_09 APPEND_ONLY specs had no PK/unique
.\waves\B9\codex-b9b-gate-close-r3-result.md:31:1. **All 8 APPEND_ONLY specs gained `natural_key=`** covering their
.\waves\B9\codex-b9b-gate-close-r3-result.md:41:     → `sa.PrimaryKeyConstraint(*natural_key, name="pk_<table>")`
.\waves\B9\codex-b9b-gate-close-r3-result.md:42:   - `APPEND_ONLY`
.\waves\B9\codex-b9b-gate-close-r3-result.md:43:     → `sa.UniqueConstraint(*natural_key, name="uq_<table>")`
.\waves\B9\codex-b9b-gate-close-r3-result.md:49:3. **Loader's APPEND_ONLY path** now branches on `spec.natural_key`:
.\waves\B9\codex-b9b-gate-close-r3-result.md:57:`tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate`:
.\waves\B9\codex-b9b-gate-close-r3-result.md:59:- Builds a SQLite table with `UniqueConstraint` over `(repl_id,
.\waves\B9\codex-b9b-gate-close-r3-result.md:71:PrimaryKeyConstraint: 99    (every UPSERT spec has a PK target)
.\waves\B9\codex-b9b-gate-close-r3-result.md:72:UniqueConstraint:       8   (every APPEND_ONLY spec has a UNIQUE target)
.\waves\B9\codex-b9b-gate-close-r3-result.md:73:Numeric(16, 6):         1   (UOM_CONVERSION_FACTOR — R1 MEDIUM 2 unchanged)
.\waves\B9\codex-b9b-gate-close-r3-result.md:94:   - `0009_fdb_tier_a.py` emits exactly 8 `UniqueConstraint` (for
.\waves\B9\codex-b9b-gate-close-r3-result.md:96:   - Loader's APPEND_ONLY path uses `on_conflict_do_nothing` when
.\waves\B9\codex-b9b-gate-close-r3-result.md:103:   - PrimaryKeyConstraint (99 UPSERT specs), or
.\waves\B9\codex-b9b-gate-close-r3-result.md:104:   - UniqueConstraint (8 APPEND_ONLY specs).
.\waves\B9\codex-b9b-gate-close-r3-result.md:108:   raise (as enforced in R1). APPEND_ONLY without natural_key now
.\waves\B9\codex-b9b-gate-close-r3-result.md:130:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"UniqueConstraint|PrimaryKeyConstraint|Numeric\\(16, 6\\)|APPEND_ONLY|on_conflict_do_nothing|test_append_only_replay\" ." in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
.\waves\B9\codex-gate-close-r2-result.md:1554:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\waves\B9\codex-gate-close-r2-result.md:1704:                                    APPEND_ONLY take the replay-safety
.\waves\B9\codex-gate-close-r2-result.md:2161:      APPEND_ONLY:
.\waves\B9\codex-gate-close-r2-result.md:2183:        Skip â€” Phase 09 backward-compat (treated as APPEND_ONLY by
.\waves\B9\codex-gate-close-r2-result.md:2209:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\waves\B9\codex-gate-close-r2-result.md:2367:{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
.\scripts\audit_column_widths.py:245:        # __table_args__ may be a tuple/list of Index/UniqueConstraint/etc.
.\modules\adjudication-engine\alembic\versions\0008_members_canonical.py:129:        sa.UniqueConstraint(
.\modules\adjudication-engine\alembic\versions\0008_members_canonical.py:184:        sa.UniqueConstraint(
.\shared\models\gov_exclusion_tables.py:35:    UniqueConstraint,
.\shared\models\gov_exclusion_tables.py:72:        UniqueConstraint(
.\modules\network-management\src\network_mgmt\models\tables.py:24:    UniqueConstraint,
.\modules\network-management\src\network_mgmt\models\tables.py:42:        UniqueConstraint(
.\modules\network-management\alembic\versions\0001_network_mgmt_baseline.py:72:        sa.UniqueConstraint(
.\shared\tests\db\test_rule_instance_seeding.py:196:def test_on_conflict_do_nothing_preserves_original():
.\shared\tests\db\test_bank_holidays_model.py:29:from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint
.\shared\tests\db\test_bank_holidays_model.py:44:        UniqueConstraint("holiday_date", "country", name="uq_bh_date_country_test"),
.\shared\tests\db\test_bank_holidays_model.py:240:    uc = next(a for a in args if isinstance(a, UniqueConstraint))
.\modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:221:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:240:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:88:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:114:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:140:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:159:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:179:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:225:        sa.PrimaryKeyConstraint("id"),
.\modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:242:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:41:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:57:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:58:        sa.UniqueConstraint("tenant_id", "trading_partner_id", "sequence_type",
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:84:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:106:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:126:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:146:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:166:        sa.PrimaryKeyConstraint("id"),
.\modules\edi-compliance\migrations\versions\0001_edi_baseline.py:182:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\tests\_fdb_delta_semantics.py:49:    UniqueConstraint,
.\modules\drug-database\tests\_fdb_delta_semantics.py:72:            For APPEND_ONLY the natural key is irrelevant for INSERT but is
.\modules\drug-database\tests\_fdb_delta_semantics.py:102:    # APPEND_ONLY tables have no conflict target; everything else needs
.\modules\drug-database\tests\_fdb_delta_semantics.py:106:            UniqueConstraint(*natural_key, name=f"uq_{table_name}_nk")
.\modules\drug-database\tests\_fdb_delta_semantics.py:120:                    # In APPEND_ONLY there can be multiple — keep the latest.
.\modules\drug-database\tests\_fdb_delta_semantics.py:132:                    # Keeps the count growth invariant of APPEND_ONLY.
.\modules\drug-database\tests\_fdb_delta_semantics.py:165:                            stmt = stmt.on_conflict_do_nothing(
.\modules\drug-database\tests\_fdb_delta_semantics.py:170:                        stmt = stmt.on_conflict_do_nothing(
.\modules\drug-database\tests\_fdb_contract.py:44:                                    APPEND_ONLY take the replay-safety
.\modules\drug-database\tests\_fdb_contract.py:511:      APPEND_ONLY:
.\modules\drug-database\tests\_fdb_contract.py:533:        Skip — Phase 09 backward-compat (treated as APPEND_ONLY by
.\modules\drug-database\tests\_fdb_contract.py:559:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\modules\core-platform\src\auth\_models.py:29:    UniqueConstraint,
.\modules\core-platform\src\auth\_models.py:86:    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)
.\modules\core-platform\src\auth\_models.py:126:        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
.\modules\core-platform\src\auth\_models.py:159:        UniqueConstraint("module", "action", name="uq_permissions_module_action"),
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:9:APPEND_ONLY) and replays cleanly (0 net new rows on second run).
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:82:_APPEND_ONLY_SPEC = TableSpec(
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:89:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:204:def test_append_only_replay_with_natural_key_does_not_duplicate(sqlite_engine) -> None:
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:205:    """B9.B R2 HIGH: APPEND_ONLY with natural_key is replay-idempotent.
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:208:    columns (mirroring what the migration emits for APPEND_ONLY specs).
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:221:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:225:    # the UniqueConstraint the migration emits).
.\modules\drug-database\tests\unit\test_fdb_tier_loader.py:248:            f"APPEND_ONLY replay duplicated: row count went from {len(n1)} "
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:1:"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:3:batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:6:and the contract template's APPEND_ONLY branch asserts row-count
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:67:# APPEND_ONLY ACD cycle
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:78:    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:80:    APPEND_ONLY semantics: every transaction grows the row count.
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:86:        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:90:    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:141:    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
.\modules\drug-database\tests\unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:412:def test_replay_uses_on_conflict_do_nothing(initial_drop, db_session):
.\modules\drug-database\tests\unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_delta_semantics.py:9:  * APPEND_ONLY history table                  → PASS (row count grows)
.\modules\drug-database\tests\unit\test_fdb_delta_semantics.py:72:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
.\modules\drug-database\tests\unit\test_fdb_delta_semantics.py:110:# APPEND_ONLY — every operation appends a row (no conflict resolution)
.\modules\drug-database\tests\unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_contract_coverage.py:9:  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
.\modules\drug-database\tests\unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\tests\unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
.\shared\db\models\sam_exclusions.py:23:    UniqueConstraint,
.\shared\db\models\sam_exclusions.py:42:        UniqueConstraint(
.\shared\db\models\oig_leie_exclusions.py:22:    UniqueConstraint,
.\shared\db\models\oig_leie_exclusions.py:41:        UniqueConstraint(
.\shared\db\models\ofac_sdn.py:27:    UniqueConstraint,
.\shared\db\models\ofac_sdn.py:86:        UniqueConstraint("ent_num", "add_num",
.\shared\db\models\ofac_sdn.py:115:        UniqueConstraint("ent_num", "alt_num",
.\shared\db\models\ofac_sdn.py:144:        UniqueConstraint("ent_num", name="uq_ofac_sdn_comments_ent_num"),
.\shared\db\models\icd10_cm_codes.py:26:    UniqueConstraint,
.\shared\db\models\icd10_cm_codes.py:50:        UniqueConstraint(
.\shared\db\models\hcpcs_codes.py:30:    UniqueConstraint,
.\shared\db\models\hcpcs_codes.py:52:        UniqueConstraint(
.\shared\db\models\core.py:36:    PrimaryKeyConstraint,
.\shared\db\models\core.py:39:    UniqueConstraint,
.\shared\db\models\core.py:130:        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
.\shared\db\models\core.py:185:        PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
.\shared\db\models\core.py:204:        UniqueConstraint("module", "action", name="uq_permissions_module_action"),
.\shared\db\models\core.py:217:        PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
.\shared\db\models\core.py:302:        UniqueConstraint(
.\shared\db\models\core.py:475:        UniqueConstraint("credential_id", name="uq_fido2_credential_id"),
.\modules\core-platform\src\notifications\models.py:13:from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
.\modules\core-platform\src\notifications\models.py:47:    __table_args__ = (UniqueConstraint("user_id", "notification_type", name="uq_pref_user_type"),)
.\shared\db\models\bank_holidays.py:23:from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint, func
.\shared\db\models\bank_holidays.py:37:        UniqueConstraint(
.\modules\drug-database\src\models\tables.py:26:    UniqueConstraint,
.\modules\drug-database\src\models\tables.py:124:        UniqueConstraint("ndc_11", "price_type", "effective_date", "data_source", name="uq_pricing_ndc_type_date_src"),
.\modules\drug-database\src\models\tables.py:219:        UniqueConstraint("tenant_id", "ndc_11", "price_type", "effective_date", name="uq_override_tenant_ndc_type_date"),
.\modules\drug-database\src\models\rxnorm_tables.py:29:    UniqueConstraint,
.\modules\drug-database\src\models\rxnorm_tables.py:56:        UniqueConstraint("rxcui", "rxaui", name="uq_rxnorm_concepts_rxcui_rxaui"),
.\modules\drug-database\src\models\rxnorm_tables.py:214:        UniqueConstraint("rxcui", "atc_code", name="uq_rxnorm_atc_crosswalk"),
.\modules\drug-database\src\models\pricing_tables.py:40:    UniqueConstraint,
.\modules\drug-database\src\models\pricing_tables.py:143:        UniqueConstraint(
.\modules\drug-database\src\models\pricing_tables.py:247:        UniqueConstraint(
.\modules\drug-database\src\models\orange_book_tables.py:42:    UniqueConstraint,
.\modules\drug-database\src\models\orange_book_tables.py:77:        UniqueConstraint(
.\modules\drug-database\src\models\orange_book_tables.py:161:        UniqueConstraint(
.\modules\drug-database\src\models\orange_book_tables.py:218:        UniqueConstraint(
.\modules\drug-database\src\models\ndc_tables.py:40:    UniqueConstraint,
.\modules\drug-database\src\models\ndc_tables.py:76:        UniqueConstraint("ndc_11", name="uq_drugs_ndc_11"),
.\modules\drug-database\src\models\ndc_tables.py:148:        UniqueConstraint("ndc_package_code_11", name="uq_drug_packages_ndc_11"),
.\modules\drug-database\src\models\fda_supplementary_tables.py:42:    UniqueConstraint,
.\modules\drug-database\src\models\fda_supplementary_tables.py:73:        UniqueConstraint("application_number", "rems_program_name", name="uq_drug_rems_pk"),
.\modules\drug-database\src\models\fda_supplementary_tables.py:134:        UniqueConstraint(
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:50:        sa.PrimaryKeyConstraint('AHFS8', name="pk_rahfsd1_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', name="pk_raplrt0_appl_relation_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', name="pk_rappltd0_fda_appl_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:77:        sa.PrimaryKeyConstraint('ATC', name="pk_ratcd0_atc_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:86:        sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', name="pk_rblasg0_substance_grp_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:104:        sa.PrimaryKeyConstraint('DCC', name="pk_rdccd0_drug_cat_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', name="pk_retcctd0_etc_change_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:122:        sa.PrimaryKeyConstraint('GTC', name="pk_rgtcd0_gen_therap_class_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', name="pk_rhicscd0_ing_stat_cd_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', name="pk_rmedcd0_med_concept_typ_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', name="pk_rmedmrd0_move_reason_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', name="pk_raplt0_appl_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:169:        sa.PrimaryKeyConstraint('GCDF', name="pk_rdosed2_dose_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:179:        sa.PrimaryKeyConstraint('HIC1_SEQN', name="pk_rhic1d2_hic_organ_sys_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:190:        sa.PrimaryKeyConstraint('HIC2_SEQN', name="pk_rhic2d3_hic_rx_class_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:202:        sa.PrimaryKeyConstraint('HIC3_SEQN', name="pk_rhic3d3_hic_therap_class_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:212:        sa.PrimaryKeyConstraint('LBLRID', name="pk_rlblrid3_lblr_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:221:        sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:233:        sa.PrimaryKeyConstraint('MEDID', name="pk_rmedst0_medid_search_term"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:242:        sa.PrimaryKeyConstraint('SEARCH_TERM_TYPE_CD', name="pk_rmedstd0_search_term_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:251:        sa.PrimaryKeyConstraint('MED_REF_DESI2_IND', name="pk_rmide2d1_ref_desi2_ind_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:260:        sa.PrimaryKeyConstraint('MED_REF_DEA_CD', name="pk_rmidead1_ref_fed_dea_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:269:        sa.PrimaryKeyConstraint('MED_REF_DESI_IND', name="pk_rmidesd1_ref_desi_ind_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:279:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', name="pk_rmidfd1_dose_form"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:291:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', name="pk_rmidfid1_routed_dose_form_med"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:300:        sa.PrimaryKeyConstraint('MED_GCNSEQNO_ASSIGN_CD', name="pk_rmigcnd1_gcnseqno_assgn_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:309:        sa.PrimaryKeyConstraint('MED_REF_GEN_THERA_EQU_CD', name="pk_rmigecd1_ref_gen_therap_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:318:        sa.PrimaryKeyConstraint('MED_REF_GEN_DRUG_NAME_CD', name="pk_rmigncd1_ref_gen_name_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:327:        sa.PrimaryKeyConstraint('MED_REF_GEN_COMP_PRICE_CD', name="pk_rmigpcd1_ref_gen_prc_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:336:        sa.PrimaryKeyConstraint('MED_REF_GEN_SPREAD_CD', name="pk_rmigscd1_ref_gen_prc_sprd_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:345:        sa.PrimaryKeyConstraint('MED_REF_INNOV_IND', name="pk_rmiinnd1_ref_innov_ind_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:354:        sa.PrimaryKeyConstraint('MED_REF_FED_LEGEND_IND', name="pk_rmilgnd1_ref_fed_lgnd_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:363:        sa.PrimaryKeyConstraint('MED_REF_MULTI_SOURCE_CD', name="pk_rmimltd1_ref_multi_src_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:372:        sa.PrimaryKeyConstraint('MED_NAME_SOURCE_CD', name="pk_rminamd1_name_src_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:381:        sa.PrimaryKeyConstraint('MED_NAME_TYPE_CD', name="pk_rminmd1_med_name_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:393:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', name="pk_rmirmid1_routed_med"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:403:        sa.PrimaryKeyConstraint('MED_ROUTE_ID', name="pk_rmirtd1_route"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:412:        sa.PrimaryKeyConstraint('MED_STATUS_CD', name="pk_rmiscd1_status_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:422:        sa.PrimaryKeyConstraint('OBC', name="pk_robcd0_obc_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:433:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiad0_attribute_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:444:        sa.PrimaryKeyConstraint('ATTRIBUTE_TYPE_CODE', name="pk_rpeiat0_attribute_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:454:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiav0_attribute_value_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:463:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeidfa0_dosage_form_attribute"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:475:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', name="pk_rpeidm0_dosage_form_mstr"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:484:        sa.PrimaryKeyConstraint('DOSAGE_FORM_TYPE_ID', name="pk_rpeidt0_dosage_form_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:493:        sa.PrimaryKeyConstraint('PATIENT_PARAM_REQ_CD', name="pk_rpeipp0_patient_param_req_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:502:        sa.PrimaryKeyConstraint('RT_LABELED_ID', name="pk_rpeirl0_rt_labeled_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:511:        sa.PrimaryKeyConstraint('STR_CONC_TYPE_ID', name="pk_rpeist0_str_conc_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:520:        sa.PrimaryKeyConstraint('UOM_TYPE_CD', name="pk_rpeiut0_uom_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:529:        sa.PrimaryKeyConstraint('CURRENCY_CD', name="pk_rprdcc0_currency_cd_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:540:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpad0_price_attr_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:549:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndctd0_ndc_attribute_typ_dsc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:559:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndcvd0_ndc_attribute_valu_dsc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:570:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_TYPE_CD', name="pk_rprdpat0_price_attr_type_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:580:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpav0_price_attr_value_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:592:        sa.PrimaryKeyConstraint('EXT_PRODUCT_CD_TYPE_ID', name="pk_rprdpcd0_ext_product_cd_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:603:        sa.PrimaryKeyConstraint('PACKAGE_TYPE_ID', name="pk_rprdpkd0_package_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:613:        sa.PrimaryKeyConstraint('FDB_PRODUCT_STATUS_CD', name="pk_rprdsd0_product_status_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:622:        sa.PrimaryKeyConstraint('PRICE_UOM_ID', name="pk_rprduom0_price_qty_uom"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:634:        sa.PrimaryKeyConstraint('GCRT', name="pk_rrouted3_route_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:646:        sa.PrimaryKeyConstraint('ROUTED_GEN_ID', name="pk_rrtgn0_routed_gen_mstr"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:655:        sa.PrimaryKeyConstraint('ROUTED_GEN_STATUS_CD', name="pk_rrtgnsd0_rtd_gen_status_dsc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:667:        sa.PrimaryKeyConstraint('STR60', name="pk_rstr1_strngth_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:676:        sa.PrimaryKeyConstraint('STRENGTH_STATUS_CODE', name="pk_rstrscd0_strength_status_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:685:        sa.PrimaryKeyConstraint('STRENGTH_TYP_CODE', name="pk_rstrtd0_strength_typ_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:696:        sa.PrimaryKeyConstraint('UOM_ID', name="pk_rstruom0_strength_uom"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:705:        sa.PrimaryKeyConstraint('TC', name="pk_rtcd0_std_therap_class_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:714:        sa.PrimaryKeyConstraint('TM_NAME_TYPE_ID', name="pk_rtmdt0_tm_name_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:723:        sa.PrimaryKeyConstraint('TM_GROUP_ID', name="pk_rtmgrpd1_tm_group_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:732:        sa.PrimaryKeyConstraint('TM_GNN_TYPE_ID', name="pk_rtmngt0_tm_gnn_type"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:741:        sa.PrimaryKeyConstraint('TM_SOURCE_ID', name="pk_rtmsrcd1_tm_source_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:752:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmdfid1_tm_routed_df_med"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:763:        sa.PrimaryKeyConstraint('MEDID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmmid1_tm_med"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:775:        sa.PrimaryKeyConstraint('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmngn0_tm_gnn"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:786:        sa.PrimaryKeyConstraint('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmnmid1_tm_med_name"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:797:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmrmid1_tm_routed_med"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:801:    # RETCHCH0_ETC_HICSEQN_HIST — tier=A delta=APPEND_ONLY record_counts_key=RETCHCH0
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:809:        sa.UniqueConstraint('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retchch0_etc_hicseqn_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:813:    # RETCHLH0_ETC_HICLSEQNO_HIST — tier=A delta=APPEND_ONLY record_counts_key=RETCHLH0
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:821:        sa.UniqueConstraint('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retchlh0_etc_hiclseqno_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:825:    # RETCNMH0_ETC_MED_NAME_ID_HIST — tier=A delta=APPEND_ONLY record_counts_key=RETCNMH0
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:833:        sa.UniqueConstraint('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retcnmh0_etc_med_name_id_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:837:    # RHICRH0_ING_HIST — tier=A delta=APPEND_ONLY record_counts_key=RHICRH0
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:843:        sa.UniqueConstraint('REPL_HIC_SEQN', 'PREV_HIC_SEQN', name="uq_rhicrh0_ing_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:847:    # RMIDFRH1_ROUTED_DOSE_FORM_HIST — tier=A delta=APPEND_ONLY record_counts_key=RMIDFRH1
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:853:        sa.UniqueConstraint('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID', name="uq_rmidfrh1_routed_dose_form_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:857:    # RMINMRH1_MED_NAME_HIST — tier=A delta=APPEND_ONLY record_counts_key=RMINMRH1
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:863:        sa.UniqueConstraint('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT', name="uq_rminmrh1_med_name_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:867:    # RMIRH1_MED_HIST — tier=A delta=APPEND_ONLY record_counts_key=RMIRH1
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:873:        sa.UniqueConstraint('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT', name="uq_rmirh1_med_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:877:    # RMIRMRH1_ROUTED_MED_HIST — tier=A delta=APPEND_ONLY record_counts_key=RMIRMRH1
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:883:        sa.UniqueConstraint('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT', name="uq_rmirmrh1_routed_med_hist"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:892:        sa.PrimaryKeyConstraint('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID', name="pk_retcsch0_etc_search"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:901:        sa.PrimaryKeyConstraint('ETC_ID', 'HIC3_SEQN', name="pk_retcxrf0_etc_hic3_etc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:910:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeial0_df_attribute_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:920:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'GCDF', name="pk_rpeigl0_gen_df_mstr_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:930:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID', name="pk_rpeiml0_med_df_mstr_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:940:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID', name="pk_rpeiol0_ovw_df_mstr_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:949:        sa.PrimaryKeyConstraint('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID', name="pk_rpeirer0_related_rt"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:958:        sa.PrimaryKeyConstraint('PARENT_RT_ID', 'CLINICAL_RT_ID', name="pk_rpeirh0_rt_hierarchy"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:967:        sa.Column('UOM_CONVERSION_FACTOR', sa.Numeric(16, 6), nullable=False),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:968:        sa.PrimaryKeyConstraint('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID', name="pk_rpeiuc0_uom_conversion"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:978:        sa.PrimaryKeyConstraint('DOSING_MODULE_UNIT_ABBREV', name="pk_runitsd0_units_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:987:        sa.PrimaryKeyConstraint('XRF_SOURCE_ID', name="pk_rxrnsrc0_source_desc"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:999:        sa.PrimaryKeyConstraint('BLA_APPL_NBR', 'APPL_TYPE_ID', 'BIOLOGICS_SN', 'MULTI_INGREDIENT_SN', name="pk_rblahic0_ingredients"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1010:        sa.PrimaryKeyConstraint('PROPRIETARY_NAME_ID', name="pk_rblapn0_proprietary_name"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1021:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'GENERIC_MED_CONCEPT_ID', name="pk_rmedmgl0_med_generic_med_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1033:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'HICL_SEQNO', name="pk_rmedmhl0_med_hiclseqno_link"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1045:        sa.PrimaryKeyConstraint('FDB_PRODUCT_ID', 'EXT_PRODUCT_CD_TYPE_ID', 'EXT_PRODUCT_CD_START_DT', 'EXT_PRODUCT_CD', name="pk_rprdpc0_ext_product_cd"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1055:        sa.PrimaryKeyConstraint('DAM_AGCSP', 'HIC_SEQN', name="pk_rxrfahx0_agcsp_hicseqn"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1064:        sa.PrimaryKeyConstraint('DACN', 'DAM_AGCSP', name="pk_rxrfddx0_dacn_agcsp"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1073:        sa.PrimaryKeyConstraint('GCDF', 'SCRIPT_QQ_ID', name="pk_rxrgdfq0_gcdf_script_qq"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1082:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', 'SCRIPT_QQ_ID', name="pk_rxrmdfq0_meddosfm_script_qq"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1094:        sa.PrimaryKeyConstraint('SCRIPT_QQ_ID', name="pk_rxrncqq0_qq_mstr"),
.\modules\drug-database\alembic\versions\0009_fdb_tier_a.py:1103:        sa.PrimaryKeyConstraint('POEUNITCDE', 'SCRIPT_QQ_ID', name="pk_rxrpdfq0_poemdosfm_script_qq"),
.\modules\drug-database\alembic\versions\0008_fdb_pricing.py:119:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0016_drop_core_exclusion_tables.py:67:        sa.PrimaryKeyConstraint("id", name=op.f("pk_exclusion_list")),
.\modules\core-platform\alembic\versions\0016_drop_core_exclusion_tables.py:133:        sa.PrimaryKeyConstraint("id", name=op.f("pk_exclusion_matches")),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:56:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:57:        sa.UniqueConstraint("rxcui", "rxaui", name="uq_rxnorm_concepts_rxcui_rxaui"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:85:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:110:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:128:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:142:        sa.PrimaryKeyConstraint("ndc_11"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:155:        sa.PrimaryKeyConstraint("id"),
.\modules\drug-database\alembic\versions\0004_rxnorm_tables.py:156:        sa.UniqueConstraint("rxcui", "atc_code", name="uq_rxnorm_atc_crosswalk"),
.\modules\core-platform\alembic\versions\0014_medical_code_refs.py:62:        sa.PrimaryKeyConstraint("id", name="pk_icd10_cm_codes"),
.\modules\core-platform\alembic\versions\0014_medical_code_refs.py:63:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0014_medical_code_refs.py:112:        sa.PrimaryKeyConstraint("id", name="pk_hcpcs_codes"),
.\modules\core-platform\alembic\versions\0014_medical_code_refs.py:113:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:67:        sa.PrimaryKeyConstraint("ent_num", name="pk_ofac_sdn"),
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:87:        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_addresses"),
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:94:        sa.UniqueConstraint("ent_num", "add_num",
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:119:        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_aliases"),
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:126:        sa.UniqueConstraint("ent_num", "alt_num",
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:154:        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_comments"),
.\modules\core-platform\alembic\versions\0012_ofac_sdn_tables.py:161:        sa.UniqueConstraint("ent_num",
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:27:for all-NK junction tables, and plain INSERT for APPEND_ONLY.
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:169:            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:173:                # NOTHING (matches the UniqueConstraint the migration
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:174:                # emits for APPEND_ONLY specs). Legacy APPEND_ONLY specs
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:178:                    stmt = stmt.on_conflict_do_nothing(
.\modules\drug-database\drug_database\services\fdb_tier_loader.py:206:                    stmt = stmt.on_conflict_do_nothing(
.\modules\core-platform\alembic\versions\0009_government_program_bins.py:81:        sa.PrimaryKeyConstraint("id", name="pk_government_program_bins"),
.\modules\core-platform\alembic\versions\0009_government_program_bins.py:84:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0008_compliance_reference_tables.py:59:        sa.PrimaryKeyConstraint("id", name="pk_oig_leie_exclusions"),
.\modules\core-platform\alembic\versions\0008_compliance_reference_tables.py:60:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0008_compliance_reference_tables.py:103:        sa.PrimaryKeyConstraint("id", name="pk_sam_exclusions"),
.\modules\core-platform\alembic\versions\0008_compliance_reference_tables.py:104:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0007_ingestion_tracking.py:81:        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
.\modules\core-platform\alembic\versions\0007_ingestion_tracking.py:127:        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_schedules")),
.\modules\core-platform\alembic\versions\0007_ingestion_tracking.py:128:        sa.UniqueConstraint(
.\modules\core-platform\alembic\versions\0006_sessions.py:65:        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:85:        return "sa.Numeric(16, 6)"
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:120:      * UPSERT_* semantics → PrimaryKeyConstraint (B9.B R1 HIGH 2)
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:121:      * APPEND_ONLY        → UniqueConstraint  (B9.B R2 HIGH —
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:126:    the LIVE row; APPEND_ONLY uses UNIQUE because history rows are
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:135:        if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:137:                f'\n        sa.UniqueConstraint({cols}, '
.\modules\drug-database\scripts\gen_fdb_tier_migration.py:142:                f'\n        sa.PrimaryKeyConstraint({cols}, '
.\modules\edi-compliance\src\models\edi_models.py:23:    UniqueConstraint,
.\modules\edi-compliance\src\models\edi_models.py:52:        UniqueConstraint("tenant_id", "isa_qualifier", "isa_id", name="uq_tp_isa"),
.\modules\edi-compliance\src\models\edi_models.py:84:        UniqueConstraint("tenant_id", "trading_partner_id", "sequence_type", name="uq_cn_seq"),
.\modules\core-platform\alembic\versions\0004_mfa_fields.py:117:        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_fido2_credentials")),
.\modules\core-platform\alembic\versions\0004_mfa_fields.py:118:        sa.UniqueConstraint("credential_id", name="uq_fido2_credential_id"),
.\modules\core-platform\alembic\versions\0003_event_bus_reliability.py:109:        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_dlq")),
.\modules\core-platform\alembic\versions\0003_event_bus_reliability.py:127:        sa.PrimaryKeyConstraint(
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
.\modules\core-platform\alembic\versions\0002_bank_holidays.py:40:        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_holidays")),
.\modules\core-platform\alembic\versions\0002_bank_holidays.py:41:        sa.UniqueConstraint(
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:75:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:99:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:115:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:135:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:150:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:165:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:184:        delta_semantics=DeltaSemantics.APPEND_ONLY,
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:38:    sa.PrimaryKeyConstraint('id', name=op.f('pk_exclusion_list')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:46:    sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:47:    sa.UniqueConstraint('module', 'action', name='uq_permissions_module_action'),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:75:    sa.PrimaryKeyConstraint('id', name=op.f('pk_tenants')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:76:    sa.UniqueConstraint('slug', name=op.f('uq_tenants_slug')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:94:    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:105:    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:121:    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:122:    sa.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:142:    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:165:    sa.PrimaryKeyConstraint('id', name=op.f('pk_exclusion_matches')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:183:    sa.PrimaryKeyConstraint('id', name=op.f('pk_files')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:199:    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_runs')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:210:    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_preferences')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:211:    sa.UniqueConstraint('user_id', 'notification_type', name='uq_notification_prefs_user_type'),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:228:    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:236:    sa.PrimaryKeyConstraint('role_id', 'permission_id', name='pk_role_permissions'),
.\modules\core-platform\alembic\versions\0001_core_baseline_core_baseline.py:247:    sa.PrimaryKeyConstraint('user_id', 'role_id', name='pk_user_roles'),
.\modules\drug-database\drug_database\services\fdb_specs.py:21:  {UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY},
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:383:          Postgres — pg_insert().on_conflict_do_nothing(constraint=
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:387:          SQLite   — sqlite_insert().on_conflict_do_nothing(index_elements=
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:438:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
.\modules\drug-database\drug_database\services\fdb_adapter.py:102:    Using this named coercer signals the generator to emit `Numeric(16, 6)`
.\modules\drug-database\drug_database\services\fdb_adapter.py:192:      APPEND_ONLY                — immutable insert (pricing history; RNP3)
.\modules\drug-database\drug_database\services\fdb_adapter.py:202:    APPEND_ONLY = "APPEND_ONLY"
.\modules\drug-database\drug_database\services\fdb_adapter.py:244:                          Phase 09 behavior (treated as APPEND_ONLY
.\modules\drug-database\drug_database\models\tables.py:26:    UniqueConstraint,
.\modules\drug-database\drug_database\models\tables.py:124:        UniqueConstraint("ndc_11", "price_type", "effective_date", "data_source", name="uq_pricing_ndc_type_date_src"),
.\modules\drug-database\drug_database\models\tables.py:219:        UniqueConstraint("tenant_id", "ndc_11", "price_type", "effective_date", name="uq_override_tenant_ndc_type_date"),
.\modules\drug-database\drug_database\models\rxnorm_tables.py:29:    UniqueConstraint,
.\modules\drug-database\drug_database\models\rxnorm_tables.py:56:        UniqueConstraint("rxcui", "rxaui", name="uq_rxnorm_concepts_rxcui_rxaui"),
.\modules\drug-database\drug_database\models\rxnorm_tables.py:214:        UniqueConstraint("rxcui", "atc_code", name="uq_rxnorm_atc_crosswalk"),
.\modules\drug-database\drug_database\models\pricing_tables.py:40:    UniqueConstraint,
.\modules\drug-database\drug_database\models\pricing_tables.py:143:        UniqueConstraint(
.\modules\drug-database\drug_database\models\pricing_tables.py:247:        UniqueConstraint(
.\modules\drug-database\drug_database\models\orange_book_tables.py:42:    UniqueConstraint,
.\modules\drug-database\drug_database\models\orange_book_tables.py:77:        UniqueConstraint(
.\modules\drug-database\drug_database\models\orange_book_tables.py:161:        UniqueConstraint(
.\modules\drug-database\drug_database\models\orange_book_tables.py:218:        UniqueConstraint(
.\modules\drug-database\drug_database\models\ndc_tables.py:40:    UniqueConstraint,
.\modules\drug-database\drug_database\models\ndc_tables.py:76:        UniqueConstraint("ndc_11", name="uq_drugs_ndc_11"),
.\modules\drug-database\drug_database\models\ndc_tables.py:148:        UniqueConstraint("ndc_package_code_11", name="uq_drug_packages_ndc_11"),
.\modules\drug-database\drug_database\models\fdb_pricing_tables.py:51:    UniqueConstraint,
.\modules\drug-database\drug_database\models\fdb_pricing_tables.py:87:        UniqueConstraint(
.\modules\drug-database\drug_database\models\fda_supplementary_tables.py:42:    UniqueConstraint,
.\modules\drug-database\drug_database\models\fda_supplementary_tables.py:73:        UniqueConstraint("application_number", "rems_program_name", name="uq_drug_rems_pk"),
.\modules\drug-database\drug_database\models\fda_supplementary_tables.py:134:        UniqueConstraint(
.\modules\dataiq\src\models\tables.py:43:        sa.UniqueConstraint("metric_key", name="uq_metric_definitions_metric_key"),
.\modules\dataiq\src\models\tables.py:109:        sa.UniqueConstraint("tenant_id", "score_date", name="uq_data_quality_scores_tenant_date"),
.\modules\dataiq\src\models\tables.py:243:        sa.UniqueConstraint(
.\modules\dataiq\src\models\tables.py:271:        sa.UniqueConstraint(
.\modules\dataiq\src\models\tables.py:306:        sa.UniqueConstraint(
.\modules\dataiq\src\models\tables.py:317:        sa.UniqueConstraint("tenant_id", name="uq_kpi_rollups_tenant_id"),
.\modules\medical-claims\src\models\tables.py:23:    UniqueConstraint,
.\modules\medical-claims\src\models\tables.py:68:        UniqueConstraint("tenant_id", "claim_number", "claim_line_number", name="uq_claim_line"),
.\modules\medical-claims\src\models\tables.py:208:        UniqueConstraint("hcpcs_code", "ndc", "effective_date", name="uq_hcpcs_ndc_date"),
.\modules\medical-claims\src\models\tables.py:238:        UniqueConstraint("hcpcs_code", "quarter", name="uq_asp_hcpcs_quarter"),
.\modules\member-management\src\models\tables.py:24:    UniqueConstraint,
.\modules\member-management\src\models\tables.py:65:        UniqueConstraint("tenant_id", "group_number", name="uq_groups_tenant_number"),
.\modules\member-management\src\models\tables.py:108:        UniqueConstraint(
.\modules\member-management\src\models\tables.py:243:        UniqueConstraint(
.\shared\data_ingestion\batching.py:412:            stmt = stmt.on_conflict_do_nothing(index_elements=self.unique_key)
.\shared\data_ingestion\batching.py:423:        stmt = stmt.on_conflict_do_nothing(index_elements=self.history.unique_key)
.\shared\data_ingestion\batching.py:688:            stmt = stmt.on_conflict_do_nothing(index_elements=unique_key)
.\modules\billing\src\models\tables.py:25:    UniqueConstraint,
.\modules\billing\src\models\tables.py:42:        UniqueConstraint("tenant_id", "auth_number", name="uq_claim_tenant_auth"),
.\modules\billing\src\models\tables.py:605:        UniqueConstraint("program_budget_id", "snapshot_date", name="uq_budget_snapshot_date"),
.\modules\billing\src\models\tables.py:818:        UniqueConstraint("tenant_id", "sequence_type", name="uq_sequence_tenant_type"),
.\modules\rules-engine\alembic\versions\0001_rules_engine_baseline.py:69:        sa.UniqueConstraint("code", name="uq_rule_type_code"),
.\modules\rules-engine\alembic\versions\0001_rules_engine_baseline.py:115:        sa.UniqueConstraint("rule_instance_id", "version", name="uq_rule_version"),
.\modules\rules-engine\src\models\tables.py:24:    UniqueConstraint,
.\modules\rules-engine\src\models\tables.py:51:        UniqueConstraint("code", name="uq_rule_type_code"),
.\modules\rules-engine\src\models\tables.py:109:        UniqueConstraint("rule_instance_id", "version", name="uq_rule_version"),
.\modules\maxacc-registry\alembic\versions\0001_maxacc_registry_baseline.py:235:        sa.UniqueConstraint(
.\modules\maxacc-registry\alembic\versions\0001_maxacc_registry_baseline.py:375:        sa.UniqueConstraint(
.\modules\program-config\src\models\tables.py:22:    UniqueConstraint,
.\modules\program-config\src\models\tables.py:86:        UniqueConstraint("tenant_id", "slug", "version", name="uq_brd_template_slug_ver"),
.\modules\program-config\src\models\tables.py:171:        UniqueConstraint("tenant_id", "external_id", name="uq_program_external_id"),
.\modules\program-config\src\models\tables.py:223:        UniqueConstraint("tenant_id", "program_id", "ndc", name="uq_program_drug_ndc"),
.\modules\program-config\src\models\tables.py:321:        UniqueConstraint("tenant_id", "program_id", name="uq_onboarding_program"),
.\modules\program-config\alembic\versions\0004_pre_b_pre_c_tables.py:66:        sa.UniqueConstraint("tenant_id", "program_id", "name", name="uq_program_network_name"),
.\modules\program-config\alembic\versions\0004_pre_b_pre_c_tables.py:135:        sa.UniqueConstraint(
.\modules\program-config\alembic\versions\0004_pre_b_pre_c_tables.py:186:        sa.UniqueConstraint(
.\modules\billing\alembic\versions\0001_billing_baseline.py:101:        sa.UniqueConstraint("tenant_id", "auth_number", name="uq_claim_tenant_auth"),
.\modules\billing\alembic\versions\0001_billing_baseline.py:513:        sa.UniqueConstraint("program_budget_id", "snapshot_date", name="uq_budget_snapshot_date"),
.\modules\billing\alembic\versions\0001_billing_baseline.py:672:        sa.UniqueConstraint("tenant_id", "sequence_type", name="uq_sequence_tenant_type"),
.\modules\program-config\alembic\versions\0001_program_config_baseline.py:62:        sa.UniqueConstraint("tenant_id", "slug", "version", name="uq_brd_template_slug_ver"),
.\modules\program-config\alembic\versions\0001_program_config_baseline.py:117:        sa.UniqueConstraint("tenant_id", "external_id", name="uq_program_external_id"),
.\modules\program-config\alembic\versions\0001_program_config_baseline.py:139:        sa.UniqueConstraint("tenant_id", "program_id", "ndc", name="uq_program_drug_ndc"),
.\modules\program-config\alembic\versions\0001_program_config_baseline.py:187:        sa.UniqueConstraint("tenant_id", "program_id", name="uq_onboarding_program"),
.\modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:112:        sa.UniqueConstraint("sdn_uid", name="uq_ofac_sdn_uid"),
.\modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:149:        sa.UniqueConstraint("idempotency_key", name="uq_submission_idempotency_key"),
.\modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:240:        sa.UniqueConstraint(
.\modules\pharmacy-directory\alembic\versions\0005_drop_pharmacy_excl_xref.py:54:        sa.PrimaryKeyConstraint("id", name="pk_pharmacy_exclusion_xref"),
.\modules\pharmacy-directory\alembic\versions\0005_drop_pharmacy_excl_xref.py:55:        sa.UniqueConstraint(
.\modules\pharmacy-directory\alembic\versions\0002_pharmacy_exclusion_xref.py:46:        sa.PrimaryKeyConstraint("id", name="pk_pharmacy_exclusion_xref"),
.\modules\pharmacy-directory\alembic\versions\0002_pharmacy_exclusion_xref.py:47:        sa.UniqueConstraint(
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:92:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacies"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:93:        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacies_ncpdp_provider_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:114:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_taxonomies"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:132:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_state_licenses"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:133:        sa.UniqueConstraint("ncpdp_provider_id", "state", "license_number", name="uq_ncpdp_stl_ncpdp_state_lic"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:172:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_services"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:173:        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacy_services_ncpdp_provider_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:195:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_remittance"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:213:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_erx_capabilities"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:231:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_medicaid"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:232:        sa.UniqueConstraint("ncpdp_provider_id", "state", name="uq_ncpdp_md_ncpdp_state"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:254:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_fwa_actions"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:274:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_coordinates"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:275:        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacy_coordinates_ncpdp_provider_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:289:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_additional_info"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:290:        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_additional_info_chain_entity_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:304:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_patient_care"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:305:        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_patient_care_chain_entity_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:319:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_programs"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:320:        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_programs_chain_entity_id"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:334:        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_recertification"),
.\modules\pharmacy-directory\alembic\versions\0001_ncpdp_tables.py:335:        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_recertification_chain_entity_id"),
.\modules\payment-processing\src\models\tables.py:20:    UniqueConstraint,
.\modules\payment-processing\src\models\tables.py:284:    __table_args__ = (UniqueConstraint("tenant_id", "vendor_adapter_id", "pay_to_entity_id"),)
.\modules\pharmacy-directory\src\models\tables.py:27:    UniqueConstraint,
.\modules\pharmacy-directory\src\models\tables.py:158:        UniqueConstraint("tenant_id", "network_code", name="uq_networks_tenant_code"),
.\modules\pharmacy-directory\src\models\tables.py:188:        UniqueConstraint(
.\modules\pharmacy-directory\src\models\tables.py:357:        UniqueConstraint("tenant_id", "pharmacy_id", name="uq_payment_info_tenant_pharmacy"),
.\modules\pharmacy-directory\src\models\ncpdp_tables.py:35:    UniqueConstraint,
.\modules\pharmacy-directory\src\models\ncpdp_tables.py:203:        UniqueConstraint(
.\modules\pharmacy-directory\src\models\ncpdp_tables.py:352:        UniqueConstraint(
.\modules\pharmacy-directory\src\models\compliance_tables.py:22:    UniqueConstraint,
.\modules\pharmacy-directory\src\models\compliance_tables.py:43:        UniqueConstraint(
.\modules\paysync\alembic\versions\0001_paysync_baseline.py:138:        sa.UniqueConstraint("tenant_id", "profile_name", name="uq_paysync_profile_name"),
.\modules\paysync\alembic\versions\0001_paysync_baseline.py:165:        sa.UniqueConstraint("tenant_id", "cycle_label", name="uq_paysync_cycle_label"),
.\modules\paysync\alembic\versions\0001_paysync_baseline.py:260:        sa.UniqueConstraint("tenant_id", "auth_num", name="uq_paysync_claim_tenant_auth"),
.\modules\paysync\alembic\versions\0004_payment_batches.py:94:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0004_payment_batches.py:153:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0003_pay_to_resolutions.py:64:        sa.UniqueConstraint("tenant_id", "claim_id", name="uq_paysync_resolution_claim"),
.\modules\prescriber-directory\alembic\versions\0007_drop_prescriber_excl_xref.py:50:        sa.PrimaryKeyConstraint("id", name="pk_prescriber_exclusion_xref"),
.\modules\prescriber-directory\alembic\versions\0007_drop_prescriber_excl_xref.py:51:        sa.UniqueConstraint(
.\modules\reporting\alembic\versions\0001_reporting_baseline.py:192:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0006_invoices.py:174:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0006_invoices.py:252:        sa.UniqueConstraint(
.\modules\prescriber-directory\alembic\versions\0005_drop_part_d_utilization.py:115:        sa.PrimaryKeyConstraint("npi", "year", name="pk_part_d_npi_year"),
.\modules\prescriber-directory\alembic\versions\0003_dea_compliance_tables.py:51:        sa.PrimaryKeyConstraint("dea_number", name="pk_dea_registrations"),
.\modules\prescriber-directory\alembic\versions\0003_dea_compliance_tables.py:81:        sa.PrimaryKeyConstraint("id", name="pk_prescriber_exclusion_xref"),
.\modules\prescriber-directory\alembic\versions\0003_dea_compliance_tables.py:82:        sa.UniqueConstraint(
.\modules\prescriber-directory\alembic\versions\0002_medicare_tables.py:104:        sa.PrimaryKeyConstraint("npi", "year", name="pk_part_d_npi_year"),
.\modules\prescriber-directory\alembic\versions\0002_medicare_tables.py:141:        sa.PrimaryKeyConstraint("npi"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:80:        sa.PrimaryKeyConstraint("id"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:81:        sa.UniqueConstraint("npi", name="uq_nppes_detail_npi"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:113:        sa.PrimaryKeyConstraint("id"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:114:        sa.UniqueConstraint("npi", "address_type", name="uq_prescriber_address_npi_type"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:131:        sa.PrimaryKeyConstraint("id"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:132:        sa.UniqueConstraint("npi", "sequence", name="uq_prescriber_taxonomy_npi_seq"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:157:        sa.PrimaryKeyConstraint("id"),
.\modules\prescriber-directory\alembic\versions\0001_nppes_tables.py:158:        sa.UniqueConstraint("npi", "sequence", name="uq_prescriber_identifier_npi_seq"),
.\modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:107:        sa.UniqueConstraint("npi", name="uq_prescriber_npi"),
.\modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:194:        sa.UniqueConstraint("prescriber_npi", "pharmacy_npi", "period_month", name="uq_ppr_npi_month"),
.\modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:214:        sa.UniqueConstraint("state_code", "provider_type", name="uq_state_provider_rule"),
.\modules\paysync\src\paysync\models\tables.py:24:    UniqueConstraint,
.\modules\paysync\src\paysync\models\tables.py:104:        UniqueConstraint("tenant_id", "profile_name", name="uq_paysync_profile_name"),
.\modules\paysync\src\paysync\models\tables.py:128:        UniqueConstraint("tenant_id", "cycle_label", name="uq_paysync_cycle_label"),
.\modules\paysync\src\paysync\models\tables.py:158:        UniqueConstraint("tenant_id", "auth_num", name="uq_paysync_claim_tenant_auth"),
.\modules\paysync\src\paysync\models\tables.py:283:        UniqueConstraint("tenant_id", "claim_id", name="uq_paysync_resolution_claim"),
.\modules\paysync\alembic\versions\0007_export_templates.py:84:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0007_export_templates.py:139:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0014_echo_sftp.py:112:        sa.UniqueConstraint(
.\modules\paysync\alembic\versions\0012_bank_settlements.py:152:        sa.UniqueConstraint("tenant_id", "adapter_name", name="uq_paysync_adapter_name"),
.\modules\plan-design\src\models\tables.py:35:    UniqueConstraint,
.\modules\plan-design\src\models\tables.py:82:        UniqueConstraint("tenant_id", "code", name="uq_program_types_tenant_code"),
.\modules\plan-design\src\models\tables.py:173:        UniqueConstraint("tenant_id", "code", name="uq_pricing_models_tenant_code"),
.\modules\plan-design\src\models\tables.py:438:        UniqueConstraint("state_code", "law_type", name="uq_state_formulary_laws_state_type"),
.\modules\reporting\src\models\tables.py:23:    UniqueConstraint,
.\modules\reporting\src\models\tables.py:174:        UniqueConstraint("user_id", "dashboard_id", name="uq_user_dashboards_user_id_dashboard_id"),
.\modules\prescriber-directory\src\models\tables.py:26:    UniqueConstraint,
.\modules\prescriber-directory\src\models\tables.py:38:        UniqueConstraint("npi", name="uq_prescriber_npi"),
.\modules\prescriber-directory\src\models\tables.py:212:        UniqueConstraint("prescriber_npi", "pharmacy_npi", "period_month", name="uq_ppr_npi_month"),
.\modules\prescriber-directory\src\models\tables.py:230:        UniqueConstraint("state_code", "provider_type", name="uq_state_provider_rule"),
.\modules\prescriber-directory\src\models\compliance_tables.py:26:    UniqueConstraint,
.\modules\prescriber-directory\src\models\compliance_tables.py:99:        UniqueConstraint(
.\modules\prescriber-directory\src\models\nppes_tables.py:23:from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
.\modules\prescriber-directory\src\models\nppes_tables.py:37:        UniqueConstraint("npi", "address_type", name="uq_prescriber_address_npi_type"),
.\modules\prescriber-directory\src\models\nppes_tables.py:65:        UniqueConstraint("npi", "sequence", name="uq_prescriber_taxonomy_npi_seq"),
.\modules\prescriber-directory\src\models\nppes_tables.py:91:        UniqueConstraint("npi", "sequence", name="uq_prescriber_identifier_npi_seq"),
.\modules\prescriber-directory\src\models\nppes_tables.py:118:        UniqueConstraint("npi", name="uq_nppes_detail_npi"),
.\modules\reclaimrx\src\reclaimrx\models\tables.py:37:    UniqueConstraint,
.\modules\reclaimrx\src\reclaimrx\models\tables.py:126:        UniqueConstraint("tenant_id", "case_number", name="uq_reclaimrx_case_number"),
.\modules\reclaimrx\src\reclaimrx\models\tables.py:334:        UniqueConstraint("tenant_id", name="uq_reclaimrx_case_seq_one_per_tenant"),
.\modules\reclaimrx\src\reclaimrx\models\tables.py:354:        UniqueConstraint("code", name="uq_reclaimrx_rule_type_code"),
.\modules\reclaimrx\src\reclaimrx\models\tables.py:386:        UniqueConstraint(
.\modules\reclaimrx\alembic\versions\0001_reclaimrx_baseline.py:243:        sa.UniqueConstraint("tenant_id", "case_number", name="uq_reclaimrx_case_number"),
.\modules\reclaimrx\alembic\versions\0001_reclaimrx_baseline.py:587:        sa.UniqueConstraint("tenant_id", name="uq_reclaimrx_case_seq_one_per_tenant"),
.\shared\data_ingestion\sources\ncpdp_dataq.py:628:                        stmt = stmt.on_conflict_do_nothing(index_elements=unique_key)
.\modules\reclaimrx\alembic\versions\0003_detection_rule_framework.py:90:        sa.UniqueConstraint("code", name="uq_reclaimrx_rule_type_code"),
.\modules\reclaimrx\alembic\versions\0003_detection_rule_framework.py:161:        sa.UniqueConstraint(
.\modules\reclaimrx\src\models\tables.py:25:    UniqueConstraint,
.\modules\reclaimrx\src\models\tables.py:81:    __table_args__ = (UniqueConstraint("tenant_id", "detection_rule_id"),)
.\modules\reclaimrx\src\models\tables.py:189:    __table_args__ = (UniqueConstraint("tenant_id", "pharmacy_npi"),)
.\modules\reclaimrx\src\models\tables.py:235:    __table_args__ = (UniqueConstraint("tenant_id", "prescriber_npi"),)
.\modules\reclaimrx\src\models\tables.py:265:    __table_args__ = (UniqueConstraint("tenant_id", "member_id"),)
.\modules\reclaimrx\src\models\tables.py:293:    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "entity_id", "snapshot_date"),)
.\modules\reclaimrx\src\models\tables.py:674:    __table_args__ = (UniqueConstraint("state_code", "rule_type"),)
.\modules\reclaimrx\src\models\tables.py:693:    __table_args__ = (UniqueConstraint("state_code", "claim_type", "violation_type", "program_type"),)
.\modules\reclaimrx\src\models\tables.py:711:    __table_args__ = (UniqueConstraint("entity_type", "entity_id"),)
.\modules\rebate-management\src\models\tables.py:47:    UniqueConstraint,
.\modules\rebate-management\src\models\tables.py:292:        UniqueConstraint(
.\modules\rebate-management\src\models\tables.py:386:        UniqueConstraint(
.\modules\rebate-management\src\models\tables.py:631:        UniqueConstraint(
.\modules\rebate-management\src\models\tables.py:683:        UniqueConstraint(
.\modules\rebate-management\src\models\tables.py:871:        UniqueConstraint(
.\modules\rebate-management\src\models\tables.py:927:        UniqueConstraint(
.\modules\reclaimrx\alembic\versions\0006_ml_detector_registry.py:73:        sa.UniqueConstraint("detector_name", name="uq_ml_detector_registry_name"),

codex
The broad search found the expected R3 surface, but the status/stat command was blocked because it combined commands. I’m narrowing now to the exact files so the verdict is based on source, not the prompt narrative.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --stat --oneline --decorate --no-renames 82617b9' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"PrimaryKeyConstraint|UniqueConstraint|Numeric\\(16, 6\\)\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "APPEND_ONLY|on_conflict_do_nothing|natural_key|schema" modules/drug-database/drug_database/services/fdb_tier_loader.py tests/unit/test_fdb_tier_loader.py modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py modules/drug-database/drug_database/services/fdb_migration_generator.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 449ms:
82617b9 (HEAD -> develop) B9.B GATE-CLOSE R2 absorption — APPEND_ONLY replay idempotency (1 HIGH residual)
 .../alembic/versions/0009_fdb_tier_a.py            |    8 +
 .../drug_database/services/fdb_tier_a/batch_09.py  |    8 +
 .../drug_database/services/fdb_tier_loader.py      |   16 +-
 .../scripts/gen_fdb_tier_migration.py              |   44 +-
 .../tests/unit/test_fdb_tier_loader.py             |   50 +
 waves/B9/codex-b9b-gate-close-r1-result.md         | 6896 ++++++++++++++++++++
 waves/B9/codex-b9b-gate-close-r2-prompt.md         |  137 +
 waves/B9/codex-b9b-gate-close-r2-result.md         | 3228 +++++++++
 waves/B9/status.md                                 |   27 +-
 9 files changed, 10394 insertions(+), 20 deletions(-)

 succeeded in 463ms:
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
?? waves/B9/codex-b9b-gate-close-r3-prompt.md
?? waves/B9/codex-b9b-gate-close-r3-result.md
warning: could not open directory '.claude/skills$skill/': No such file or directory

 succeeded in 456ms:
50:        sa.PrimaryKeyConstraint('AHFS8', name="pk_rahfsd1_desc"),
59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', name="pk_raplrt0_appl_relation_type"),
68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', name="pk_rappltd0_fda_appl_type"),
77:        sa.PrimaryKeyConstraint('ATC', name="pk_ratcd0_atc_desc"),
86:        sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', name="pk_rblasg0_substance_grp_desc"),
104:        sa.PrimaryKeyConstraint('DCC', name="pk_rdccd0_drug_cat_desc"),
113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', name="pk_retcctd0_etc_change_type_desc"),
122:        sa.PrimaryKeyConstraint('GTC', name="pk_rgtcd0_gen_therap_class_desc"),
131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', name="pk_rhicscd0_ing_stat_cd_desc"),
140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', name="pk_rmedcd0_med_concept_typ_desc"),
149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', name="pk_rmedmrd0_move_reason_desc"),
159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', name="pk_raplt0_appl_type"),
169:        sa.PrimaryKeyConstraint('GCDF', name="pk_rdosed2_dose_desc"),
179:        sa.PrimaryKeyConstraint('HIC1_SEQN', name="pk_rhic1d2_hic_organ_sys_desc"),
190:        sa.PrimaryKeyConstraint('HIC2_SEQN', name="pk_rhic2d3_hic_rx_class_desc"),
202:        sa.PrimaryKeyConstraint('HIC3_SEQN', name="pk_rhic3d3_hic_therap_class_desc"),
212:        sa.PrimaryKeyConstraint('LBLRID', name="pk_rlblrid3_lblr_desc"),
221:        sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
233:        sa.PrimaryKeyConstraint('MEDID', name="pk_rmedst0_medid_search_term"),
242:        sa.PrimaryKeyConstraint('SEARCH_TERM_TYPE_CD', name="pk_rmedstd0_search_term_type_desc"),
251:        sa.PrimaryKeyConstraint('MED_REF_DESI2_IND', name="pk_rmide2d1_ref_desi2_ind_desc"),
260:        sa.PrimaryKeyConstraint('MED_REF_DEA_CD', name="pk_rmidead1_ref_fed_dea_desc"),
269:        sa.PrimaryKeyConstraint('MED_REF_DESI_IND', name="pk_rmidesd1_ref_desi_ind_desc"),
279:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', name="pk_rmidfd1_dose_form"),
291:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', name="pk_rmidfid1_routed_dose_form_med"),
300:        sa.PrimaryKeyConstraint('MED_GCNSEQNO_ASSIGN_CD', name="pk_rmigcnd1_gcnseqno_assgn_desc"),
309:        sa.PrimaryKeyConstraint('MED_REF_GEN_THERA_EQU_CD', name="pk_rmigecd1_ref_gen_therap_desc"),
318:        sa.PrimaryKeyConstraint('MED_REF_GEN_DRUG_NAME_CD', name="pk_rmigncd1_ref_gen_name_desc"),
327:        sa.PrimaryKeyConstraint('MED_REF_GEN_COMP_PRICE_CD', name="pk_rmigpcd1_ref_gen_prc_desc"),
336:        sa.PrimaryKeyConstraint('MED_REF_GEN_SPREAD_CD', name="pk_rmigscd1_ref_gen_prc_sprd_desc"),
345:        sa.PrimaryKeyConstraint('MED_REF_INNOV_IND', name="pk_rmiinnd1_ref_innov_ind_desc"),
354:        sa.PrimaryKeyConstraint('MED_REF_FED_LEGEND_IND', name="pk_rmilgnd1_ref_fed_lgnd_desc"),
363:        sa.PrimaryKeyConstraint('MED_REF_MULTI_SOURCE_CD', name="pk_rmimltd1_ref_multi_src_desc"),
372:        sa.PrimaryKeyConstraint('MED_NAME_SOURCE_CD', name="pk_rminamd1_name_src_desc"),
381:        sa.PrimaryKeyConstraint('MED_NAME_TYPE_CD', name="pk_rminmd1_med_name_type_desc"),
393:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', name="pk_rmirmid1_routed_med"),
403:        sa.PrimaryKeyConstraint('MED_ROUTE_ID', name="pk_rmirtd1_route"),
412:        sa.PrimaryKeyConstraint('MED_STATUS_CD', name="pk_rmiscd1_status_desc"),
422:        sa.PrimaryKeyConstraint('OBC', name="pk_robcd0_obc_desc"),
433:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiad0_attribute_desc"),
444:        sa.PrimaryKeyConstraint('ATTRIBUTE_TYPE_CODE', name="pk_rpeiat0_attribute_type_desc"),
454:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiav0_attribute_value_desc"),
463:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeidfa0_dosage_form_attribute"),
475:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', name="pk_rpeidm0_dosage_form_mstr"),
484:        sa.PrimaryKeyConstraint('DOSAGE_FORM_TYPE_ID', name="pk_rpeidt0_dosage_form_type"),
493:        sa.PrimaryKeyConstraint('PATIENT_PARAM_REQ_CD', name="pk_rpeipp0_patient_param_req_desc"),
502:        sa.PrimaryKeyConstraint('RT_LABELED_ID', name="pk_rpeirl0_rt_labeled_desc"),
511:        sa.PrimaryKeyConstraint('STR_CONC_TYPE_ID', name="pk_rpeist0_str_conc_type"),
520:        sa.PrimaryKeyConstraint('UOM_TYPE_CD', name="pk_rpeiut0_uom_type_desc"),
529:        sa.PrimaryKeyConstraint('CURRENCY_CD', name="pk_rprdcc0_currency_cd_desc"),
540:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpad0_price_attr_desc"),
549:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndctd0_ndc_attribute_typ_dsc"),
559:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndcvd0_ndc_attribute_valu_dsc"),
570:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_TYPE_CD', name="pk_rprdpat0_price_attr_type_desc"),
580:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpav0_price_attr_value_desc"),
592:        sa.PrimaryKeyConstraint('EXT_PRODUCT_CD_TYPE_ID', name="pk_rprdpcd0_ext_product_cd_desc"),
603:        sa.PrimaryKeyConstraint('PACKAGE_TYPE_ID', name="pk_rprdpkd0_package_desc"),
613:        sa.PrimaryKeyConstraint('FDB_PRODUCT_STATUS_CD', name="pk_rprdsd0_product_status_desc"),
622:        sa.PrimaryKeyConstraint('PRICE_UOM_ID', name="pk_rprduom0_price_qty_uom"),
634:        sa.PrimaryKeyConstraint('GCRT', name="pk_rrouted3_route_desc"),
646:        sa.PrimaryKeyConstraint('ROUTED_GEN_ID', name="pk_rrtgn0_routed_gen_mstr"),
655:        sa.PrimaryKeyConstraint('ROUTED_GEN_STATUS_CD', name="pk_rrtgnsd0_rtd_gen_status_dsc"),
667:        sa.PrimaryKeyConstraint('STR60', name="pk_rstr1_strngth_desc"),
676:        sa.PrimaryKeyConstraint('STRENGTH_STATUS_CODE', name="pk_rstrscd0_strength_status_desc"),
685:        sa.PrimaryKeyConstraint('STRENGTH_TYP_CODE', name="pk_rstrtd0_strength_typ_desc"),
696:        sa.PrimaryKeyConstraint('UOM_ID', name="pk_rstruom0_strength_uom"),
705:        sa.PrimaryKeyConstraint('TC', name="pk_rtcd0_std_therap_class_desc"),
714:        sa.PrimaryKeyConstraint('TM_NAME_TYPE_ID', name="pk_rtmdt0_tm_name_type"),
723:        sa.PrimaryKeyConstraint('TM_GROUP_ID', name="pk_rtmgrpd1_tm_group_desc"),
732:        sa.PrimaryKeyConstraint('TM_GNN_TYPE_ID', name="pk_rtmngt0_tm_gnn_type"),
741:        sa.PrimaryKeyConstraint('TM_SOURCE_ID', name="pk_rtmsrcd1_tm_source_desc"),
752:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmdfid1_tm_routed_df_med"),
763:        sa.PrimaryKeyConstraint('MEDID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmmid1_tm_med"),
775:        sa.PrimaryKeyConstraint('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmngn0_tm_gnn"),
786:        sa.PrimaryKeyConstraint('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmnmid1_tm_med_name"),
797:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmrmid1_tm_routed_med"),
809:        sa.UniqueConstraint('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retchch0_etc_hicseqn_hist"),
821:        sa.UniqueConstraint('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retchlh0_etc_hiclseqno_hist"),
833:        sa.UniqueConstraint('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO', name="uq_retcnmh0_etc_med_name_id_hist"),
843:        sa.UniqueConstraint('REPL_HIC_SEQN', 'PREV_HIC_SEQN', name="uq_rhicrh0_ing_hist"),
853:        sa.UniqueConstraint('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID', name="uq_rmidfrh1_routed_dose_form_hist"),
863:        sa.UniqueConstraint('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT', name="uq_rminmrh1_med_name_hist"),
873:        sa.UniqueConstraint('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT', name="uq_rmirh1_med_hist"),
883:        sa.UniqueConstraint('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT', name="uq_rmirmrh1_routed_med_hist"),
892:        sa.PrimaryKeyConstraint('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID', name="pk_retcsch0_etc_search"),
901:        sa.PrimaryKeyConstraint('ETC_ID', 'HIC3_SEQN', name="pk_retcxrf0_etc_hic3_etc"),
910:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeial0_df_attribute_link"),
920:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'GCDF', name="pk_rpeigl0_gen_df_mstr_link"),
930:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID', name="pk_rpeiml0_med_df_mstr_link"),
940:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID', name="pk_rpeiol0_ovw_df_mstr_link"),
949:        sa.PrimaryKeyConstraint('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID', name="pk_rpeirer0_related_rt"),
958:        sa.PrimaryKeyConstraint('PARENT_RT_ID', 'CLINICAL_RT_ID', name="pk_rpeirh0_rt_hierarchy"),
967:        sa.Column('UOM_CONVERSION_FACTOR', sa.Numeric(16, 6), nullable=False),
968:        sa.PrimaryKeyConstraint('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID', name="pk_rpeiuc0_uom_conversion"),
978:        sa.PrimaryKeyConstraint('DOSING_MODULE_UNIT_ABBREV', name="pk_runitsd0_units_desc"),
987:        sa.PrimaryKeyConstraint('XRF_SOURCE_ID', name="pk_rxrnsrc0_source_desc"),
999:        sa.PrimaryKeyConstraint('BLA_APPL_NBR', 'APPL_TYPE_ID', 'BIOLOGICS_SN', 'MULTI_INGREDIENT_SN', name="pk_rblahic0_ingredients"),
1010:        sa.PrimaryKeyConstraint('PROPRIETARY_NAME_ID', name="pk_rblapn0_proprietary_name"),
1021:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'GENERIC_MED_CONCEPT_ID', name="pk_rmedmgl0_med_generic_med_link"),
1033:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'HICL_SEQNO', name="pk_rmedmhl0_med_hiclseqno_link"),
1045:        sa.PrimaryKeyConstraint('FDB_PRODUCT_ID', 'EXT_PRODUCT_CD_TYPE_ID', 'EXT_PRODUCT_CD_START_DT', 'EXT_PRODUCT_CD', name="pk_rprdpc0_ext_product_cd"),
1055:        sa.PrimaryKeyConstraint('DAM_AGCSP', 'HIC_SEQN', name="pk_rxrfahx0_agcsp_hicseqn"),
1064:        sa.PrimaryKeyConstraint('DACN', 'DAM_AGCSP', name="pk_rxrfddx0_dacn_agcsp"),
1073:        sa.PrimaryKeyConstraint('GCDF', 'SCRIPT_QQ_ID', name="pk_rxrgdfq0_gcdf_script_qq"),
1082:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', 'SCRIPT_QQ_ID', name="pk_rxrmdfq0_meddosfm_script_qq"),
1094:        sa.PrimaryKeyConstraint('SCRIPT_QQ_ID', name="pk_rxrncqq0_qq_mstr"),
1103:        sa.PrimaryKeyConstraint('POEUNITCDE', 'SCRIPT_QQ_ID', name="pk_rxrpdfq0_poemdosfm_script_qq"),

2026-05-12T15:30:10.230039Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.5 seconds
Output:
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:52:        natural_key=('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:75:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:76:        natural_key=('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:99:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:100:        natural_key=('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:115:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:116:        natural_key=('REPL_HIC_SEQN', 'PREV_HIC_SEQN'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:135:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:136:        natural_key=('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:150:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:151:        natural_key=('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:165:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:166:        natural_key=('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:184:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:185:        natural_key=('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_loader.py:25:The loader uses INSERT ... ON CONFLICT (natural_key) DO UPDATE for
modules/drug-database/drug_database/services/fdb_tier_loader.py:26:UPSERT_BY_NATURAL_KEY semantics, ON CONFLICT (natural_key) DO NOTHING
modules/drug-database/drug_database/services/fdb_tier_loader.py:27:for all-NK junction tables, and plain INSERT for APPEND_ONLY.
modules/drug-database/drug_database/services/fdb_tier_loader.py:101:    schema: str = "drug_database",
modules/drug-database/drug_database/services/fdb_tier_loader.py:115:        schema: target Postgres schema (default "drug_database").
modules/drug-database/drug_database/services/fdb_tier_loader.py:138:    # schema="" → no schema prefix (test seam for SQLite which has no real
modules/drug-database/drug_database/services/fdb_tier_loader.py:139:    # schemas). Production callers leave the default `drug_database`.
modules/drug-database/drug_database/services/fdb_tier_loader.py:140:    md = MetaData(schema=schema) if schema else MetaData()
modules/drug-database/drug_database/services/fdb_tier_loader.py:169:            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
modules/drug-database/drug_database/services/fdb_tier_loader.py:172:                # the spec declares natural_key, use ON CONFLICT DO
modules/drug-database/drug_database/services/fdb_tier_loader.py:174:                # emits for APPEND_ONLY specs). Legacy APPEND_ONLY specs
modules/drug-database/drug_database/services/fdb_tier_loader.py:175:                # without natural_key fall through to plain INSERT (will
modules/drug-database/drug_database/services/fdb_tier_loader.py:177:                if spec.natural_key:
modules/drug-database/drug_database/services/fdb_tier_loader.py:178:                    stmt = stmt.on_conflict_do_nothing(
modules/drug-database/drug_database/services/fdb_tier_loader.py:179:                        index_elements=list(spec.natural_key)
modules/drug-database/drug_database/services/fdb_tier_loader.py:187:                if not spec.natural_key:
modules/drug-database/drug_database/services/fdb_tier_loader.py:190:                        f"natural_key; got empty."
modules/drug-database/drug_database/services/fdb_tier_loader.py:193:                    c for c in spec.columns if c not in spec.natural_key
modules/drug-database/drug_database/services/fdb_tier_loader.py:200:                        index_elements=list(spec.natural_key),
modules/drug-database/drug_database/services/fdb_tier_loader.py:206:                    stmt = stmt.on_conflict_do_nothing(
modules/drug-database/drug_database/services/fdb_tier_loader.py:207:                        index_elements=list(spec.natural_key)
rg: tests/unit/test_fdb_tier_loader.py: The system cannot find the path specified. (os error 3)
rg: modules/drug-database/drug_database/services/fdb_migration_generator.py: The system cannot find the file specified. (os error 2)

 exited 1 in 478ms:
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:52:        natural_key=('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:75:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:76:        natural_key=('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:99:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:100:        natural_key=('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:115:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:116:        natural_key=('REPL_HIC_SEQN', 'PREV_HIC_SEQN'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:135:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:136:        natural_key=('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:150:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:151:        natural_key=('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:165:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:166:        natural_key=('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:184:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:185:        natural_key=('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_loader.py:25:The loader uses INSERT ... ON CONFLICT (natural_key) DO UPDATE for
modules/drug-database/drug_database/services/fdb_tier_loader.py:26:UPSERT_BY_NATURAL_KEY semantics, ON CONFLICT (natural_key) DO NOTHING
modules/drug-database/drug_database/services/fdb_tier_loader.py:27:for all-NK junction tables, and plain INSERT for APPEND_ONLY.
modules/drug-database/drug_database/services/fdb_tier_loader.py:101:    schema: str = "drug_database",
modules/drug-database/drug_database/services/fdb_tier_loader.py:115:        schema: target Postgres schema (default "drug_database").
modules/drug-database/drug_database/services/fdb_tier_loader.py:138:    # schema="" → no schema prefix (test seam for SQLite which has no real
modules/drug-database/drug_database/services/fdb_tier_loader.py:139:    # schemas). Production callers leave the default `drug_database`.
modules/drug-database/drug_database/services/fdb_tier_loader.py:140:    md = MetaData(schema=schema) if schema else MetaData()
modules/drug-database/drug_database/services/fdb_tier_loader.py:169:            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
modules/drug-database/drug_database/services/fdb_tier_loader.py:172:                # the spec declares natural_key, use ON CONFLICT DO
modules/drug-database/drug_database/services/fdb_tier_loader.py:174:                # emits for APPEND_ONLY specs). Legacy APPEND_ONLY specs
modules/drug-database/drug_database/services/fdb_tier_loader.py:175:                # without natural_key fall through to plain INSERT (will
modules/drug-database/drug_database/services/fdb_tier_loader.py:177:                if spec.natural_key:
modules/drug-database/drug_database/services/fdb_tier_loader.py:178:                    stmt = stmt.on_conflict_do_nothing(
modules/drug-database/drug_database/services/fdb_tier_loader.py:179:                        index_elements=list(spec.natural_key)
modules/drug-database/drug_database/services/fdb_tier_loader.py:187:                if not spec.natural_key:
modules/drug-database/drug_database/services/fdb_tier_loader.py:190:                        f"natural_key; got empty."
modules/drug-database/drug_database/services/fdb_tier_loader.py:193:                    c for c in spec.columns if c not in spec.natural_key
modules/drug-database/drug_database/services/fdb_tier_loader.py:200:                        index_elements=list(spec.natural_key),
modules/drug-database/drug_database/services/fdb_tier_loader.py:206:                    stmt = stmt.on_conflict_do_nothing(
modules/drug-database/drug_database/services/fdb_tier_loader.py:207:                        index_elements=list(spec.natural_key)
rg: tests/unit/test_fdb_tier_loader.py: The system cannot find the path specified. (os error 3)
rg: modules/drug-database/drug_database/services/fdb_migration_generator.py: The system cannot find the file specified. (os error 2)

codex
The target commit is at `HEAD` and the migration grep shows the claimed 99 PK plus 8 UNIQUE pattern around batch 09. I also see unrelated dirty worktree state, so I’m treating this strictly as a review of `82617b9` and the referenced B9.B files.
2026-05-12T15:30:31.843419Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'PrimaryKeyConstraint').Count"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'PrimaryKeyConstraint').Count" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'UniqueConstraint').Count" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'PrimaryKeyConstraint').Count"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'UniqueConstraint').Count"` rejected: blocked by policy
2026-05-12T15:30:31.843827Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'UniqueConstraint').Count"` rejected: blocked by policy
2026-05-12T15:30:31.976939Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'Numeric\\(16, 6\\)').Count"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'Numeric\\(16, 6\\)').Count" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path 'modules/drug-database/alembic/versions/0009_fdb_tier_a.py' -Pattern 'Numeric\\(16, 6\\)').Count"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"test_append_only_replay|load_tier_group|UniqueConstraint|schema=\\\"\\\"|assert.*count|select\\(func.count\" modules/drug-database/tests tests modules/drug-database -g \"test_fdb_tier_loader.py\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T15:30:32.377808Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
rg: regex parse error:
    (?:test_append_only_replay|load_tier_group|UniqueConstraint|schema=\)
    ^
error: unclosed group

 exited 1 in 397ms:
rg: regex parse error:
    (?:test_append_only_replay|load_tier_group|UniqueConstraint|schema=\)
    ^
error: unclosed group

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --count "PrimaryKeyConstraint" modules/drug-database/alembic/versions/0009_fdb_tier_a.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --count "UniqueConstraint" modules/drug-database/alembic/versions/0009_fdb_tier_a.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --count \"Numeric\\(16, 6\\)\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "test_append_only_replay|load_tier_group|UniqueConstraint|schema=|func.count|assert.*1" modules/drug-database/tests tests -g "test_fdb_tier_loader.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 421ms:
99

 succeeded in 432ms:
8

 succeeded in 429ms:
1

 succeeded in 452ms:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:3:Tests the `load_tier_group` dispatcher against an in-memory SQLite
modules/drug-database/tests\unit\test_fdb_tier_loader.py:107:# load_tier_group behaviors
modules/drug-database/tests\unit\test_fdb_tier_loader.py:111:def test_load_tier_group_filters_by_group(sqlite_engine) -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:113:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:127:        result = load_tier_group(
modules/drug-database/tests\unit\test_fdb_tier_loader.py:136:def test_load_tier_group_dry_run_parses_but_does_not_write(sqlite_engine) -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:138:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:145:        result = load_tier_group(
modules/drug-database/tests\unit\test_fdb_tier_loader.py:150:    assert summary.rows_parsed == 1
modules/drug-database/tests\unit\test_fdb_tier_loader.py:154:def test_load_tier_group_unsupported_semantics_skipped(sqlite_engine) -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:156:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:170:        result = load_tier_group(
modules/drug-database/tests\unit\test_fdb_tier_loader.py:175:    assert summary.rows_parsed == 1
modules/drug-database/tests\unit\test_fdb_tier_loader.py:176:    assert summary.skipped == 1
modules/drug-database/tests\unit\test_fdb_tier_loader.py:179:def test_load_tier_group_upsert_requires_natural_key() -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:181:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:198:            load_tier_group(
modules/drug-database/tests\unit\test_fdb_tier_loader.py:204:def test_append_only_replay_with_natural_key_does_not_duplicate(sqlite_engine) -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:213:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:225:    # the UniqueConstraint the migration emits).
modules/drug-database/tests\unit\test_fdb_tier_loader.py:237:    # Run 1 — inserts the row.  schema="" matches the schemaless SQLite test table.
modules/drug-database/tests\unit\test_fdb_tier_loader.py:239:        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
modules/drug-database/tests\unit\test_fdb_tier_loader.py:241:        assert len(n1) == 1
modules/drug-database/tests\unit\test_fdb_tier_loader.py:245:        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
modules/drug-database/tests\unit\test_fdb_tier_loader.py:247:        assert len(n2) == 1, (
modules/drug-database/tests\unit\test_fdb_tier_loader.py:254:def test_load_tier_group_summary_aggregates_per_table(sqlite_engine) -> None:
modules/drug-database/tests\unit\test_fdb_tier_loader.py:256:    from drug_database.services.fdb_tier_loader import load_tier_group
modules/drug-database/tests\unit\test_fdb_tier_loader.py:273:        result = load_tier_group(
modules/drug-database/tests\unit\test_fdb_tier_loader.py:278:    assert result.table_summaries["RFOO_TEST"].rows_parsed == 1

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/drug_database/services/fdb_tier_loader.py' | Select-Object -Skip 150 -First 70" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/scripts/gen_fdb_tier_migration.py' | Select-Object -Skip 70 -First 90" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_fdb_tier_loader.py' | Select-Object -Skip 204 -First 48" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py' | Select-Object -Skip 35 -First 160" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 481ms:
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
                # B9.B R2 HIGH mitigation â€” same-drop replay must produce
                # 0 net new rows for the SC-7 idempotency contract. If
                # the spec declares natural_key, use ON CONFLICT DO
                # NOTHING (matches the UniqueConstraint the migration
                # emits for APPEND_ONLY specs). Legacy APPEND_ONLY specs
                # without natural_key fall through to plain INSERT (will
                # duplicate on replay â€” caller is responsible).
                if spec.natural_key:
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=list(spec.natural_key)
                    )
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

 succeeded in 480ms:
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

    When `spec.natural_key` is non-empty, emits a uniqueness surface
    so Postgres `ON CONFLICT (natural_key)` resolves to a real
    constraint:

      * UPSERT_* semantics â†’ PrimaryKeyConstraint (B9.B R1 HIGH 2)
      * APPEND_ONLY        â†’ UniqueConstraint  (B9.B R2 HIGH â€”
                              gives same-drop replay idempotency
                              via ON CONFLICT DO NOTHING)

    UPSERT uses PK because the natural-key tuple uniquely identifies
    the LIVE row; APPEND_ONLY uses UNIQUE because history rows are
    immutable but the same logical fact may legitimately arrive
    multiple times across drops and must be de-duped, not error.
    """
    table_name = spec.table_name.lower()  # FDB names are upper; DB tables snake_case
    rcounts_key = spec.record_counts_key or spec.table_name
    constraint_line = ""
    if spec.natural_key:
        cols = ", ".join(repr(c) for c in spec.natural_key)
        if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
            constraint_line = (
                f'\n        sa.UniqueConstraint({cols}, '
                f'name="uq_{table_name}"),'
            )
        else:
            constraint_line = (
                f'\n        sa.PrimaryKeyConstraint({cols}, '
                f'name="pk_{table_name}"),'
            )
    return f"""    # {spec.table_name} â€” tier={spec.tier.value} delta={spec.delta_semantics.value} record_counts_key={rcounts_key}
    op.create_table(
        "{table_name}",
{_column_block(spec)}{constraint_line}
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

 succeeded in 491ms:
    """B9.B R2 HIGH: APPEND_ONLY with natural_key is replay-idempotent.

    Constructs a SQLite table with a UNIQUE index over the natural_key
    columns (mirroring what the migration emits for APPEND_ONLY specs).
    First load inserts the row; second load is `INSERT ... ON CONFLICT
    (natural_key) DO NOTHING` â€” row count must stay the same.
    """
    from sqlalchemy import Index
    from drug_database.services.fdb_tier_loader import load_tier_group

    hist_spec = TableSpec(
        table_name="RFOO_HIST",
        columns=("repl_id", "prev_id", "eff_dt"),
        coercers={"repl_id": int, "prev_id": int, "eff_dt": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=("repl_id", "prev_id", "eff_dt"),
    )
    # Create the table WITH a UNIQUE index over natural_key (mirrors
    # the UniqueConstraint the migration emits).
    md = MetaData()
    table = Table(
        "rfoo_hist", md,
        *(Column(c, String) for c in hist_spec.columns),
    )
    Index("uq_rfoo_hist", *(table.c[c] for c in hist_spec.natural_key), unique=True)
    md.create_all(sqlite_engine)

    adapter = _FakeAdapter({"RFOO_HIST": [{"repl_id": "42", "prev_id": "41", "eff_dt": "20260101"}]})
    drop = adapter.discover_latest_drop()

    # Run 1 â€” inserts the row.  schema="" matches the schemaless SQLite test table.
    with Session(sqlite_engine) as session:
        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
        n1 = session.execute(select(table)).all()
        assert len(n1) == 1

    # Run 2 (same drop, same data) â€” must NOT add a duplicate.
    with Session(sqlite_engine) as session:
        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
        n2 = session.execute(select(table)).all()
        assert len(n2) == 1, (
            f"APPEND_ONLY replay duplicated: row count went from {len(n1)} "
            f"to {len(n2)} after second load. The ON CONFLICT DO NOTHING "
            f"path is regressed."
        )


 succeeded in 501ms:
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "HIC_SEQN": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCHCH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # ETC change history â€” HICL_SEQNO-keyed
    TableSpec(
        table_name="RETCHLH0_ETC_HICLSEQNO_HIST",
        columns=(
            "HICL_SEQNO",
            "ETC_ID",
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "HICL_SEQNO": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCHLH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # ETC change history â€” MED_NAME_ID-keyed
    TableSpec(
        table_name="RETCNMH0_ETC_MED_NAME_ID_HIST",
        columns=(
            "MED_NAME_ID",
            "ETC_ID",
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "MED_NAME_ID": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCNMH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # Ingredient renumber history
    TableSpec(
        table_name="RHICRH0_ING_HIST",
        columns=("REPL_HIC_SEQN", "PREV_HIC_SEQN", "HIC_REPL_EFF_DT"),
        coercers={
            "REPL_HIC_SEQN": int,
            "PREV_HIC_SEQN": int,
            "HIC_REPL_EFF_DT": _parse_fdb_date,
        },
        nullable=frozenset({"HIC_REPL_EFF_DT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHICRH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('REPL_HIC_SEQN', 'PREV_HIC_SEQN'),
    ),
    # Routed dose-form med id replacement history
    TableSpec(
        table_name="RMIDFRH1_ROUTED_DOSE_FORM_HIST",
        columns=(
            "MED_REPL_ROUTED_DF_MED_ID",
            "MED_PREV_ROUTED_DF_MED_ID",
            "MED_ROUTED_DF_MED_ID_REP_EF_DT",
        ),
        coercers={
            "MED_REPL_ROUTED_DF_MED_ID": int,
            "MED_PREV_ROUTED_DF_MED_ID": int,
            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
        },
        nullable=frozenset({"MED_ROUTED_DF_MED_ID_REP_EF_DT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDFRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID'),
    ),
    # Med name id replacement history
    TableSpec(
        table_name="RMINMRH1_MED_NAME_HIST",
        columns=("MED_REPL_NAME_ID", "MED_PREV_NAME_ID", "MED_NAME_ID_REPL_EFF_DT"),
        coercers={
            "MED_REPL_NAME_ID": int,
            "MED_PREV_NAME_ID": int,
            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMINMRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT'),
    ),
    # MEDID replacement history
    TableSpec(
        table_name="RMIRH1_MED_HIST",
        columns=("MED_REPL_MEDID", "MED_PREV_MEDID", "MED_MEDID_REPL_EFF_DT"),
        coercers={
            "MED_REPL_MEDID": int,
            "MED_PREV_MEDID": int,
            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT'),
    ),
    # Routed med id replacement history
    TableSpec(
        table_name="RMIRMRH1_ROUTED_MED_HIST",
        columns=(
            "MED_REPL_ROUTED_MED_ID",
            "MED_PREV_ROUTED_MED_ID",
            "MED_ROUTED_MED_ID_REPL_EFF_DT",
        ),
        coercers={
            "MED_REPL_ROUTED_MED_ID": int,
            "MED_PREV_ROUTED_MED_ID": int,
            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRMRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT'),
    ),
]


__all__ = ["SPECS"]

codex
The loader and generator changes match the intended shape: APPEND_ONLY branches to `on_conflict_do_nothing(index_elements=list(spec.natural_key))`, and the generator emits UNIQUE for APPEND_ONLY while keeping PK for UPSERT. One small accounting caveat is visible: the loader increments `summary.inserted` even when DO NOTHING suppresses a duplicate, but this does not affect replay row-count idempotency.
2026-05-12T15:31:27.355534Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate -p no:cacheprovider'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate -p no:cacheprovider' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate -p no:cacheprovider'` rejected: blocked by policy
2026-05-12T15:31:27.488782Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py -p no:cacheprovider'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py -p no:cacheprovider' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "UPSERT semantics requires|APPEND_ONLY|UniqueConstraint|PrimaryKeyConstraint" modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py modules/drug-database/scripts/gen_fdb_tier_migration.py modules/drug-database/tests/unit/test_fdb_tier_loader.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_tier_loader.py modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py -p no:cacheprovider'` rejected: blocked by policy
 succeeded in 408ms:
modules/drug-database/tests/unit/test_fdb_tier_loader.py:9:APPEND_ONLY) and replays cleanly (0 net new rows on second run).
modules/drug-database/tests/unit/test_fdb_tier_loader.py:82:_APPEND_ONLY_SPEC = TableSpec(
modules/drug-database/tests/unit/test_fdb_tier_loader.py:89:    delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit/test_fdb_tier_loader.py:205:    """B9.B R2 HIGH: APPEND_ONLY with natural_key is replay-idempotent.
modules/drug-database/tests/unit/test_fdb_tier_loader.py:208:    columns (mirroring what the migration emits for APPEND_ONLY specs).
modules/drug-database/tests/unit/test_fdb_tier_loader.py:221:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit/test_fdb_tier_loader.py:225:    # the UniqueConstraint the migration emits).
modules/drug-database/tests/unit/test_fdb_tier_loader.py:248:            f"APPEND_ONLY replay duplicated: row count went from {len(n1)} "
modules/drug-database/scripts/gen_fdb_tier_migration.py:120:      * UPSERT_* semantics → PrimaryKeyConstraint (B9.B R1 HIGH 2)
modules/drug-database/scripts/gen_fdb_tier_migration.py:121:      * APPEND_ONLY        → UniqueConstraint  (B9.B R2 HIGH —
modules/drug-database/scripts/gen_fdb_tier_migration.py:126:    the LIVE row; APPEND_ONLY uses UNIQUE because history rows are
modules/drug-database/scripts/gen_fdb_tier_migration.py:135:        if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
modules/drug-database/scripts/gen_fdb_tier_migration.py:137:                f'\n        sa.UniqueConstraint({cols}, '
modules/drug-database/scripts/gen_fdb_tier_migration.py:142:                f'\n        sa.PrimaryKeyConstraint({cols}, '

codex
Test execution is blocked by the current command policy in this read-only session, even with pytest cache disabled. I’m continuing with static verification and the committed test body; I’ll call out that limitation in the verdict.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "requires natural_key|natural_key; got empty|UPSERT_WITH_EFFECTIVE_DATE|UPSERT_BY_NATURAL_KEY|raise ValueError" modules/drug-database/scripts/gen_fdb_tier_migration.py modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py modules/drug-database/drug_database/services/fdb_tier_loader.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "natural_key=|delta_semantics=DeltaSemantics" modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/scripts/gen_fdb_tier_migration.py' | Select-Object -Skip 150 -First 80" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py' | Select-Object -Skip 1 -First 220" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 exited 1 in 429ms:
rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

2026-05-12T15:31:48.079410Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

 succeeded in 458ms:
modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py:85:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_loader.py:26:UPSERT_BY_NATURAL_KEY semantics, ON CONFLICT (natural_key) DO NOTHING
modules/drug-database/drug_database/services/fdb_tier_loader.py:184:                DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_loader.py:185:                DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/drug_database/services/fdb_tier_loader.py:188:                    raise ValueError(
modules/drug-database/drug_database/services/fdb_tier_loader.py:190:                        f"natural_key; got empty."
modules/drug-database/scripts/gen_fdb_tier_migration.py:49:# raise ValueError — the operator must extend this table explicitly
modules/drug-database/scripts/gen_fdb_tier_migration.py:67:        raise ValueError(
modules/drug-database/scripts/gen_fdb_tier_migration.py:87:    raise ValueError(
modules/drug-database/scripts/gen_fdb_tier_migration.py:250:        raise ValueError("generate_tier_migration: empty specs list")
modules/drug-database/scripts/gen_fdb_tier_migration.py:252:        DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/scripts/gen_fdb_tier_migration.py:253:        DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/scripts/gen_fdb_tier_migration.py:257:            raise ValueError(
modules/drug-database/scripts/gen_fdb_tier_migration.py:267:            raise ValueError(

 succeeded in 488ms:


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

 succeeded in 499ms:

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

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/scripts/gen_fdb_tier_migration.py' | Select-Object -Skip 238 -First 45" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py' | Select-Object -Skip 145 -First 110" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n --glob 'batch_*.py' \"natural_key=|delta_semantics=DeltaSemantics\" modules/drug-database/drug_database/services/fdb_tier_a" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 481ms:

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

 succeeded in 493ms:
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

 succeeded in 445ms:
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
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:52:        natural_key=('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:75:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:76:        natural_key=('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:99:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:100:        natural_key=('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:115:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:116:        natural_key=('REPL_HIC_SEQN', 'PREV_HIC_SEQN'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:135:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:136:        natural_key=('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:150:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:151:        natural_key=('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:165:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:166:        natural_key=('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:184:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:185:        natural_key=('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT'),
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

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --count "natural_key=" modules/drug-database/drug_database/services/fdb_tier_a' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --count \"delta_semantics=DeltaSemantics\\.APPEND_ONLY\" modules/drug-database/drug_database/services/fdb_tier_a" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --count \"delta_semantics=DeltaSemantics\\.UPSERT\" modules/drug-database/drug_database/services/fdb_tier_a" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --files modules/drug-database/drug_database/services/fdb_tier_a' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 477ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:12
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:8
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:5
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:11
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:11

 succeeded in 533ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:8

 succeeded in 545ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:11
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:12
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:11
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:10
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:11
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:11
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:5
modules/drug-database/drug_database/services/fdb_tier_a\__init__.py:1

 succeeded in 555ms:
modules/drug-database/drug_database/services/fdb_tier_a\__init__.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py

2026-05-12T15:32:29.058241Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -c "from drug_database.services.fdb_tier_a import SPECS; from drug_database.services.fdb_adapter import DeltaSemantics; print(len(SPECS)); print(sum(1 for s in SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.delta_semantics is not DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.natural_key)); print([s.table_name for s in SPECS if not s.natural_key])"'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -c "from drug_database.services.fdb_tier_a import SPECS; from drug_database.services.fdb_adapter import DeltaSemantics; print(len(SPECS)); print(sum(1 for s in SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.delta_semantics is not DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.natural_key)); print([s.table_name for s in SPECS if not s.natural_key])"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -c "from drug_database.services.fdb_tier_a import SPECS; from drug_database.services.fdb_adapter import DeltaSemantics; print(len(SPECS)); print(sum(1 for s in SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.delta_semantics is not DeltaSemantics.APPEND_ONLY)); print(sum(1 for s in SPECS if s.natural_key)); print([s.table_name for s in SPECS if not s.natural_key])"'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/drug_database/services/fdb_tier_loader.py' | Select-Object -First 155" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 481ms:
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

    # schema="" â†’ no schema prefix (test seam for SQLite which has no real
    # schemas). Production callers leave the default `drug_database`.
    md = MetaData(schema=schema) if schema else MetaData()
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

codex
GO — B9.B can close; B9.C can open.

Verified from `82617b9` / `HEAD`:

- Migration counts match: `99` `PrimaryKeyConstraint`, `8` `UniqueConstraint`, `1` `Numeric(16, 6)` in [0009_fdb_tier_a.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:809).
- The 8 UNIQUE constraints are exactly the batch_09 APPEND_ONLY history tables.
- APPEND_ONLY loader path now uses `on_conflict_do_nothing(index_elements=list(spec.natural_key))` when `natural_key` is present in [fdb_tier_loader.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:169).
- All 8 batch_09 specs declare `natural_key` in [batch_09.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:51).
- Generator still hard-fails UPSERT specs without `natural_key`, while allowing APPEND_ONLY without one for legacy compatibility in [gen_fdb_tier_migration.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:252). That asymmetry is defensible.
- Replay-idempotency test runs the loader twice and asserts the second load does not increase row count in [test_fdb_tier_loader.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/unit/test_fdb_tier_loader.py:204).

No residual HIGH/MEDIUM blockers found.

Two non-blocking notes: I could not execute pytest in this read-only command-policy session, so this R3 verdict is static verification plus your reported `787 passed`. Also, the loader still increments `summary.inserted` after `DO NOTHING`; row-count idempotency is correct, but that counter is not an actual inserted-row count on conflict.
tokens used
58,282
GO — B9.B can close; B9.C can open.

Verified from `82617b9` / `HEAD`:

- Migration counts match: `99` `PrimaryKeyConstraint`, `8` `UniqueConstraint`, `1` `Numeric(16, 6)` in [0009_fdb_tier_a.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:809).
- The 8 UNIQUE constraints are exactly the batch_09 APPEND_ONLY history tables.
- APPEND_ONLY loader path now uses `on_conflict_do_nothing(index_elements=list(spec.natural_key))` when `natural_key` is present in [fdb_tier_loader.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:169).
- All 8 batch_09 specs declare `natural_key` in [batch_09.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:51).
- Generator still hard-fails UPSERT specs without `natural_key`, while allowing APPEND_ONLY without one for legacy compatibility in [gen_fdb_tier_migration.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:252). That asymmetry is defensible.
- Replay-idempotency test runs the loader twice and asserts the second load does not increase row count in [test_fdb_tier_loader.py](C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/unit/test_fdb_tier_loader.py:204).

No residual HIGH/MEDIUM blockers found.

Two non-blocking notes: I could not execute pytest in this read-only command-policy session, so this R3 verdict is static verification plus your reported `787 passed`. Also, the loader still increments `summary.inserted` after `DO NOTHING`; row-count idempotency is correct, but that counter is not an actual inserted-row count on conflict.
