# Wave B12 — Status (Retroactive Ledger)

**Last updated:** 2026-05-18
**State:** PARTIALLY EXECUTED — 7 of 10 items DONE per backlog snapshot, 3 OPEN (S1, S7, S8); subsequent partial fixes landed inside B10-w5

> Retroactive ledger scaffolding. B12 was scaffolded with 8 slices
> (S1-S8) but did not run through a formal codex spec consult before
> work landed.

---

## Slice scope (S1-S8)

Captured from session memory observations on B12 charter:

| Slice | Status | Notes |
|---|---|---|
| S1 | Pre-landed in B10-w5 | `_shim/auth.current_user` JWT decode (B11 polish merged) |
| S2 | Pre-landed in B10-w5 | Prescriber index (B11 polish merged) |
| S3 | DONE | Per backlog snapshot |
| S4 | DONE | Per backlog snapshot |
| S5 | DONE | Per backlog snapshot |
| S6 | DONE | Per backlog snapshot |
| S7 | Pre-landed in B10-w5 | F-004 login hydration — `useSearchParams` Suspense wrap (commit `43f0613d merge(b12-s7)`) |
| S8 | Pre-landed in B10-w5 | Schema name fix `drug_db → drug_database` (commit `cc7f9a92 fix(s8)`) |

---

## Three sub-branches identified per session memory observation 712

| Branch | Scope | Completion state |
|---|---|---|
| `wave/B10-w5-b12-s1-shim-auth` | S1 — auth JWT decode | Merged to B10-w5 |
| `wave/B10-w5-b12-s7-login-suspense` | S7 — login hydration fix | Merged to B10-w5 |
| `wave/B10-w5-b12-fixes` | General B12 fixes | Locked worktree at HEAD `2b4dbff9` |

---

## Open items

- S1, S7, S8 marked OPEN in last formal backlog snapshot but appear to have landed via the sub-branches above. **Reconciliation needed** between formal backlog and actual ship state.
- Orphaned-code triage was deferred per session memory observation 699.

---

## Cross-references

- `waves/B10/status.md` (current active wave — receiving partial B12 work)
- `waves/B11/status.md` (sister polish wave)
- `framework/disciplines/wave-control-ledger.md` (Werkbench)
