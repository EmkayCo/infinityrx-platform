# Codex B9.A mini-GATE-CLOSE R2 — Verification Pass

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.A close (verification of R1 GO-WITH-FIXES absorption)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Round 1 result:** GO-WITH-FIXES (2 HIGH + 2 MEDIUM) — see
`waves/B9/codex-gate-close-r1-result.md`

## What changed since R1

One absorption commit on `develop` — `33e858b`:

```
B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
```

Fixes applied:

### F1 — MTL REVOKE template (HIGH 1)
File: `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl`
- Documented `{{APP_ROLES_QUOTED}}` placeholder (was used at line 80
  but undocumented in the header).
- Removed broken schema-prefix-broadcast assumption from the REVOKE
  clause. Was: `ON {{SCHEMA}}.{{MTL_TABLES}}` (qualified only the
  first table). Now: `ON {{MTL_TABLES}}` with the migration helper
  responsible for emitting fully-qualified `drug_database.mtl_x`
  entries per table.
- Header now contains a reference Python substitution body for the
  B9.G migration helper.
- New test `modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py`
  (6 tests) renders the template with realistic inputs and asserts:
  * No `{{...}}` placeholder survives a full substitution
  * Every table appears schema-qualified (catches the line-43 bug)
  * Verification block uses quoted role literals
  * REVOKE statement appears exactly once

### F2 — Wave artifacts in repo (HIGH 2)
Mirrored the following from Werkbench into `waves/B9/`:
- `status.md` (the ledger)
- `parse_warning_allowlist.md` (empty initial — only the policy table)
- `phase09_compat_baseline.md`
- `module_base_profile.md`
- `write_path_enforcement.md`

Pattern matches existing `waves/B7.2/`, `waves/B8/`, etc.

### F3 — Parse-warning allowlist enforcement (MEDIUM 1)
File: `modules/drug-database/tests/_fdb_contract.py`
- Added `load_parse_warning_allowlist(path=None)` that reads
  `waves/B9/parse_warning_allowlist.md` and returns ONLY entries
  inside the "Approved allowlist entries" section (regex section-
  anchored — surrounding doc text and policy tables ignored).
- 4 new tests:
  * `test_allowlist_loader_returns_empty_on_repo_initial` — empty
    initial state is a contract (B9.A C3 ships empty)
  * `test_allowlist_loader_parses_approved_table_rows` — happy path
    + section-anchoring assertion (rows in "Process for adding"
    section are NOT returned)
  * `test_allowlist_loader_handles_missing_approved_section` —
    file without the section → empty set, no error
  * `test_allowlist_loader_raises_on_missing_file` — empty file
    MUST exist per B9.A ship contract

### F4 — Delta-contract coverage assertion (MEDIUM 2)
Explicitly deferred to B9.B per codex's own remediation language:
"In B9.B, add a registry-vs-contract coverage test...". Documented
as a B9.B pre-opening obligation in `waves/B9/status.md` →
"B9.B pre-opening obligation (F4)".

## Test result after absorption

```
B9.A cumulative tests:  116 → 129 PASS (+13: 6 MTL render + 4 allowlist + 3 prior reconciliation)
drug-database unit:      326 → 332 PASS, no regression
integration:             3 skipped (live-DB only, expected)
```

## Areas to verify in R2

1. **F1**: does the new MTL template substitution recipe correctly
   substitute all four placeholders in `_render`
   (`modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py`)?
   Is the no-`{{...}}`-survives assertion the right invariant?
2. **F2**: are the in-repo `waves/B9/` artifacts complete enough
   that a future operator can reconstruct B9.A close from this
   checkout alone (no Werkbench dependency)?
3. **F3**: is the regex anchoring on "Approved allowlist entries"
   robust to operator edits of the surrounding markdown (e.g.,
   renaming the H2)? If renamed, the loader returns empty — is
   that the right failure mode, or should it raise?
4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
   obligation sufficient documentation for the deferral, or should
   a stub test land in B9.A now with `pytest.mark.xfail(reason=...)`?

## Verdict format

GO — B9.A closes; B9.B opens.
GO-WITH-FIXES — list residual HIGH / MEDIUM concerns.
NO-GO — fundamental issue.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |
