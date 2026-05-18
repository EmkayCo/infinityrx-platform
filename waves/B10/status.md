# Wave B10 — Status (Retroactive Ledger)

**Last updated:** 2026-05-18
**Branch:** `wave/B10-w5` (week 5 of B10 sequence)
**State:** ACTIVE — substantial work shipped; deferred follow-ups pending

> This file was scaffolded retroactively to close a Werkbench
> wave-control-ledger discipline gap. Earlier B10 weeks (w1-w4) and
> the formal charter were not captured in this folder during their
> execution.

---

## What shipped on `wave/B10-w5` in this cycle

### SP-0 — Integration Foundation (Plans A-D)
Composition portal wiring, framework selection, gateway pattern, host layer, qa-harness scaffold. Reference: `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` + plan files `docs/superpowers/plans/2026-05-15-sp0-plan-*.md`.

### SP-1 — PaySync Operator Portal (5 plans, A-E)
Full financial-processing module: upload→inbox→cycles→batches→files→journal. 94 commits on sub-branch `wave/B10-w5-sp1-paysync`. Acceptance: `docs/sp-1-acceptance.md`. Codex gate-close: NO-GO with 7 BLOCKs (1 resolved via branch reorg, 6 deferred per ship-with-gaps decision — see `docs/sp1-deferred-followups.md`). NOT YET MERGED to `wave/B10-w5`.

### SP-2 — Directories Portal / Reference Data Control Plane (5 plans, A-E)
Federated search spine + 6 browse clusters + Cmd+K + ingestion console + quality dashboard + audit viewer + alert dismissal + E2E round-trip. 462 directories-package tests, 0 skips, codex GO across all 5 plans. Acceptance: `docs/sp-2-acceptance.md`. MERGED to `wave/B10-w5` at `2207e945` + follow-up fix at `671f63ff` (audit useQuery cache key).

### Other landings (background polish on `wave/B10-w5`)
- B9.C Tier B FDW scaffolding (72 specs, alembic 0010, FDW manifest 131→203)
- B11 polish backports (107 tests, 5/5 R1 BLOCKS resolved, NextAuth wiring, prescriber index, _shim/auth JWT decode)
- B12 partial fixes pre-landed (F-W04 audit-gate via S1, prescriber index via S2)

---

## Active sub-branches under B10

| Branch | State | Notes |
|---|---|---|
| `wave/B10-w5` | tip = `671f63ff` (origin synced) | Main integration line; SP-0 + SP-2 + B9 + B11 + B12-partial all merged |
| `wave/B10-w5-sp1-paysync` | tip = `661f0d9c` (origin synced) | SP-1 ship-with-gaps; followups doc committed; NOT merged to wave/B10-w5 pending F1-F6 |
| `wave/B10-w5-sp2-integration` | stale at `8ba58c01` | Pre-Plan-E SP-2 state; superseded by main wave/B10-w5 — candidate for deletion |
| 20+ `wave/B10-w5-*` sub-branches | various (locked in worktrees) | Parallel cleanup/refactor branches from earlier in B10 wave |

---

## Codex gate artifacts

| Gate | File | Verdict |
|---|---|---|
| SP-1 spec/plan rounds | `docs/superpowers/codex-sp1-review-r1.md`, `r2.md` | r1 NO-GO → r2 GO-WITH-CHANGES |
| SP-1 gate-close | `docs/superpowers/codex-sp1-paysync-gate-close-r1.md` | NO-GO with 7 BLOCKs (1 resolved, 6 deferred) |
| SP-2 spec | `docs/superpowers/codex-sp2-spec-review-r1.md` | r3 GO after 3 rounds |
| SP-2 plan-write | (inline in commits `6fd65cdb`..`d1bc59d0` and equivalents) | r6 GO after 5 rounds |
| SP-2 Plan A gate-close | (agent return report) | GO |
| SP-2 Plan B gate-close | (agent return report) | GO first-pass |
| SP-2 Plan C gate-close | (agent return report) | GO r2 |
| SP-2 Plan D gate-close + recovery | (agent return reports) | GO r2 after 5 commits + recovery from agent-termination |
| SP-2 Plan E gate-close | (agent return report) | GO r5 (Playwright APIRequestContext + CORS preflight issues resolved) |

---

## Deferred follow-ups (tracked elsewhere)

- **SP-1 F1-F6** — see `docs/sp1-deferred-followups.md` (Echo gate, active stubs, TenantScopedMixin, E2E skip, test skips, coverage)
- **SP-2 Plan D — AuditLogPage useQuery cache key** — RESOLVED at commit `671f63ff` (was task #15)
- **Wave ledger drift** — RESOLVED by this scaffolding pass

---

## Next decisions

1. SP-1 merge to `wave/B10-w5` — blocked on F1-F6 completion
2. Cleanup of 22 locked worktrees from prior sessions
3. Branch hygiene — many `wave/B10-w5-*` sub-branches; some merged, some abandoned

---

## Cross-references

- `docs/superpowers/SP-1-LAUNCH.md`, `docs/superpowers/SP-2-LAUNCH.md`
- `docs/sp-1-acceptance.md`, `docs/sp-2-acceptance.md`, `docs/sp1-deferred-followups.md`
- `framework/disciplines/wave-control-ledger.md` (Werkbench)
- `waves/B11/status.md`, `waves/B12/status.md`
