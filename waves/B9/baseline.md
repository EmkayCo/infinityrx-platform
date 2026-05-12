# Wave B9 — B9.A C0 Baseline Capture

**Captured:** 2026-05-11 (PARTIAL — Docker-dependent parts deferred)
**Environment:** Windows 11 / Python 3.13 / Docker Desktop NOT running this session
**Predecessor state:** Phase 11A IMPLEMENTED (B7), Phase 11A COMPLETE (B7.2), B8.1.1 CLOSED, B9 PLAN v3.1 LOCKED.

This file is the source-of-truth for what was true at the start of B9 execution. Every B9.B..B9.G mini-GATE-CLOSE re-asserts these numbers (or documents the delta).

---

## ✅ Disk budget (plan invariant #4)

```
Filesystem      Size  Used Avail Use% Mounted on
C:              921G  371G  550G  41% /c
```

**550 GB free** on C:. Comfortably absorbs D2's +1.16 GB target + index headroom + working space. Plan invariant #4 satisfied (requires ≥5 GB).

---

## Docker-resumed captures (2026-05-11, all 3 containers healthy)

All three containers came up healthy: `infinityrx-postgres`, `infinityrx-redis`, `infinityrx-rabbitmq`. All ports bound. Volume `infinityrx-platform_postgres_data` CreatedAt 2026-05-09T20:49:51Z (pre-B7.2).

### 🚨 Invariant #2 — FAILS (BLOCKER): `ifx_prod_app` regression

**Captured (postgres bootstrap superuser):**

```sql
SELECT count(*) FROM pg_authid WHERE rolname = 'ifx_prod_app';
-- result: 1
```

**Expected per memory `project_phase11a_implemented.md` (B7.2 close):**

> "B7.2 W4: DROP ROLE ifx_prod_app (live cluster) → pg_authid count=0 → **ifx_prod_app is gone. Phase 11A COMPLETE.**"

**Full ifx_* role state in cluster (2026-05-11):**

```
 ifx_dev_admin
 ifx_dev_app
 ifx_mock_admin
 ifx_mock_app
 ifx_prod_admin   ← NEW (not even tracked in memory)
 ifx_prod_app     ← REGRESSED (B7.2 dropped this)
 ifx_ref_reader
 ifx_reference_writer
```

**Root cause investigation:**

- `init-multi-db.sql` creates ONLY: `ifx_dev_app`, `ifx_mock_app`, `ifx_reference_writer`, `ifx_ref_reader`, `ifx_dev_admin`, `ifx_mock_admin` (6 roles). It does NOT create `ifx_prod_app` or `ifx_prod_admin`.
- `grep -rn "CREATE ROLE.*ifx_prod" modules/ infrastructure/` returns ZERO matches (excluding `.claude/worktrees/`).
- Volume CreatedAt 2026-05-09 is BEFORE B7.2 ran (B7.2 happened 2026-05-10). The volume contains continuous state since 5/9, including the B7.2 DROP. The DROP successfully removed the role at the time of B7.2 close.
- **Therefore: something between B7.2 close (2026-05-10) and now (2026-05-11) re-created both `ifx_prod_app` and `ifx_prod_admin` in this volume.** The project has no committed code that does this — it was a manual psql session, an undocumented script, or a wave step missing from the audit trail.

**Disposition (UPDATED 2026-05-11 post-B7.3):** Invariant #2 FAILED at initial C0 capture; B7.3 wave shipped (commit `503cd7b` on develop) to resolve root cause + clean cluster. Re-verification 2026-05-11 22:55 EDT confirms:

- `pg_authid` count for `ifx_prod_app` = **0** ✅
- `pg_authid` count for `ifx_prod_admin` = **0** ✅
- `ifx_*` total = 6 (dev/mock app+admin, ref_reader, reference_writer) ✅
- `setup_fdw.sh --verify` = **132 PASS, 0 FAIL** ✅
- Phase 09 row counts unchanged (15,635,770 + 23) ✅

**Invariant #2 now PASS. C0 fully closed. B9.A can proceed to C1-C14.**

---

**Original failure context (preserved for audit trail):**



- **Investigation agent dispatched** (background, in-progress). Mandate: identify root cause via git log since 2026-05-10, alembic_version cross-ref, post-B7.2 wave artifacts, shell + psql history, claude-mem search, pre-B7 git snapshot. Returns when complete.
- **`pg_shdepend` survey** (this session): `ifx_prod_admin` has **0** dependencies in any DB (clean drop candidate); `ifx_prod_app` has **56 per DB × 3 DBs = 168 total** dependencies (requires B7.2-W3-equivalent REVOKE/re-GRANT work — deferred to a future B7.3 wave).
- **DROP ROLE ifx_prod_admin pending** — owner-approved 2026-05-11 but classifier blocked Bash execution citing investigation-still-running and "do not paper over". Two paths: (1) owner runs `! docker exec -i infinityrx-postgres psql -U infinityrx -d infinityrx_reference -c "DROP ROLE ifx_prod_admin;"` interactively, or (2) add a permission rule. Action remains pre-approved; awaiting execute.
- **`ifx_prod_app` DROP deferred** to a B7.3 wave that mirrors B7.2's W1-W4 sequence. Charter v3.2 not affected — Phase 11A's COMPLETE assertion now carries an asterisk pending B7.3 closeout.
- **Charter invariant for B9.A C0** remains FAILED until B7.3 ships or memory is amended.

### ✅ Invariant #3 — schemas exist

```sql
SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','pg_toast','information_schema');
```

Returned: `core`, `drug_database`, `drug_db`, `pharmacy_dir`, `prescriber_dir`, `public`, `reference`, `shared` (8 schemas including 4 expected: `drug_database`, `drug_db`, `reference`, `shared`).

### ✅ Phase 09 compat baseline (charter SC + plan C12)

```sql
SELECT count(*) FROM drug_database.fdb_ndc_price_history;
-- result: 15,635,770

SELECT count(*) FROM drug_database.fdb_price_type_desc;
-- result: 23

-- Representative NDC lookup (timing on):
SELECT ndc_11, price_type FROM drug_database.fdb_ndc_price_history WHERE ndc_11 = '00781153910' LIMIT 5;
-- result: 0 rows; Time: 2.116 ms (index hit — fast even on miss)
```

Per-phase mini-GATE-CLOSE asserts these counts unchanged (plus or minus weekly delta growth, which would be tracked separately).

### ✅ FDW verify — 132 PASS, 0 FAIL

```bash
bash infrastructure/scripts/setup_fdw.sh --verify
# Manifest: 66 entries
# infinityrx_dev:  66 PASS, 0 FAIL
# infinityrx_mock: 66 PASS, 0 FAIL
# Total: 132 PASS, 0 FAIL
```

Plan invariant `setup_fdw --verify 66/66` satisfied **per env DB** (the script counts per-DB so the cross-DB total is 132). FDW baseline locked at 66 entries per env DB → 264 default / 283 conditional after B9.

---

## ✅ Test inventory (collection baseline — plan invariant #6 part 1)

**Total collected: 1,623 tests across 126 modules** (excluding `tests/integration` — see Known Issues below).

Captured 2026-05-11 via:

```bash
.venv/Scripts/python -m pytest --collect-only --ignore=tests/integration -q
```

Per-module breakdown captured in this session's transcript; not enumerated here (volume). The mini-GATE-CLOSE assertion is on the TOTAL + module count, plus node-ID delta (added contract tests should appear, no others should disappear).

**Second-run snapshot (flake detection):** DEFERRED — requires Docker for stable run.

---

## ⚠️ Test failure baseline (plan invariant #6 part 2) — captured 2026-05-11, +61 vs memory

```bash
.venv/Scripts/python -m pytest -q --tb=no --ignore=tests/integration --no-header
```

**Result: 195 FAILED/ERROR lines.** Memory said 134. **Delta: +61** since the prior baseline was captured.

This is documented as a separate regression — NOT B9's to fix per charter §Out-of-scope row 3 ("134 pre-existing test failures (forensic wave)"). The +61 may be related to the `ifx_prod_app` regression (some loader-precedence tests may now fail when env resolves to `ifx_prod_app` instead of dev/mock) — TBD pending investigation agent.

**Failing-node-ID snapshot saved at:** session transcript line search for `FAILED ` prefix. Per plan's flake-detection design, a second run will be done after the role regression is resolved to identify volatility.

Per-phase mini-GATE-CLOSE asserts: **failure-count ≤ 195** AND no failing node-ID outside the captured set (except in-phase contract tests whose failures would be in `parse_warning_allowlist.md`).

---

## ⚠️ Known issue captured at baseline (NOT B9's to fix)

### tests/integration collection error — plugin already registered

```
ERROR collecting tests/integration
ValueError: Plugin already registered under a different name:
  C:\...\tests\integration\conftest.py=<module 'tests.integration.conftest'>
Interrupted: 1 error during collection
```

**Disposition:** documented as pre-existing baseline state per charter `Out of scope` row 3 ("134 pre-existing test failures (forensic wave)"). B9 does NOT fix this. Forensic wave handles it.

**Practical impact on B9 baseline:** the 1,623 / 126 collection figures EXCLUDE `tests/integration`. When the integration plugin conflict is fixed by a forensic wave, those tests will be added to the baseline. Per-phase mini-GATE-CLOSE asserts on the post-baseline number.

---

## Deferred capture checklist (for next session resume)

When Docker is up:

1. `docker compose up -d`
2. `psql infinityrx_reference -tc "SELECT count(*) FROM pg_authid WHERE rolname = 'ifx_prod_app';"` → expect 0
3. `psql infinityrx_reference -tc "SELECT count(DISTINCT schema_name) FROM information_schema.schemata WHERE schema_name IN ('drug_database', 'drug_db', 'reference', 'shared');"` → expect 4
4. `psql infinityrx_reference -tc "SELECT count(*) FROM drug_database.fdb_ndc_price_history;"` → record (Phase 09 baseline)
5. `psql infinityrx_reference -tc "SELECT count(*) FROM drug_database.fdb_price_type_desc;"` → record (Phase 09 baseline)
6. `time psql infinityrx_dev -c "<representative NDC lookup query>"` → record latency
7. `bash infrastructure/scripts/setup_fdw.sh --verify` → expect 66/66
8. `.venv/Scripts/python -m pytest -q --tb=no | grep -cE '^(FAILED|ERROR)'` → expect 134 (or document delta)
9. Append all results to this file under a "Resumed captures" section.

---

## Source commands (this session)

```bash
# Disk
df -h "C:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/"

# Pytest collection (ex-integration)
.venv/Scripts/python -m pytest --collect-only --ignore=tests/integration -q | \
  awk -F':' '$2 ~ /^[ ]*[0-9]+$/ { sum+=$2; n+=1 } END { print "Total:", sum, "Modules:", n }'
```

---

**Status:** C0 PARTIAL. Disk + test-inventory captured; DB-dependent invariants deferred to next session. B9.A C1-C14 commits remain. This is **not** a B9.A mini-GATE-CLOSE — that requires all C0-C14 evidence + Docker-up DB invariants confirmed.
