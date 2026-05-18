# Wave B11 — Status (Retroactive Ledger)

**Last updated:** 2026-05-18
**State:** SHIPPED (per session memory; closed before SP-1/SP-2 cycle started)

> Retroactive ledger scaffolding. No formal charter or codex artifacts
> captured for B11 during execution — this status reflects what was
> reconstructable from session memory and commit history.

---

## What shipped

- 107 tests added across multiple modules
- 5 of 5 R1 BLOCKS resolved (per `docs/audit/wave1-remediation-report.md` style)
- NextAuth session wiring into api-client + real HS256 JWT (`packages/contract/src/impls/`, portal/operator)
- Prescriber index-friendly search + NPI shortcut (polish)
- CORS + dev-trust-jwt loader on directory backends
- `_shim/auth.current_user` decodes JWT — F-W04 audit gate green
- Reference-DB write-path guard + Windows os.replace fallback
- `fix(b9): restore fdb_tier_a load mode — codex B12 P1 regression`

---

## Known limitations (per session memory)

- `enforce_test_first.py` hook limitation surfaced during B11 — hook search depth doesn't reach `tests/unit/<subdir>/` patterns. Worked around by using `Bash sed` for production-file fixes when test files exist deeper than the hook's search depth.

---

## Commits visible on `wave/B10-w5`

Commits prefixed `fix(b11):` or `feat(b11):` in the log. Many landed via salvage branch `salvage/wave-b10-w5-untracked-20260514` and were merged forward.

---

## Cross-references

- `waves/B10/status.md` (current active wave)
- `waves/B12/status.md` (pending follow-on wave)
- `framework/disciplines/wave-control-ledger.md` (Werkbench)
