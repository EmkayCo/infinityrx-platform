# SP-3 Plan A5 Sub-Session

**Date:** 2026-05-18
**Agent:** plan-writer (contract + frontend)
**Plan output:** `docs/superpowers/plans/2026-05-18-sp3-plan-a5-contract-frontend.md`

## What was done

Read the full spec (`docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`), the deep
audit (`waves/B10/SP-3-audit-deep.md`), the SP-2 Plan A reference
(`docs/superpowers/plans/2026-05-17-sp2-plan-a-search-spine.md`), and all four
prescriber-directory contract files to anchor the exact pattern before writing.

Key ground-truth facts locked before writing:

- **Contract layout:** `src/impls/<domain>/` with 4 files — confirmed from audit §5 and direct
  file reads. NO `clients/`, `schemas/`, or `cache/` subdirectories (these were the spec's
  incorrect assumption).
- **EventEnvelope fields:** `event_type` (not `type`), `timestamp` (not `emitted_at`), `source_module`
  required — confirmed from audit §2.
- **Existing portal pages:** 7 pages already exist at `portal/operator/app/reclaimrx/`. Plan A5
  adds only the 6 NEW routes from spec §6. Does not touch existing pages (surgical changes rule).
- **Manifest:** `packages/shell/src/_generated/manifest.json` confirmed at HEAD with `modules:
  ["prescriber-directory", "directories"]`. Reclaimrx added as third entry.
- **No `packages/modules/reclaimrx/`** exists — clean slate confirmed.

## Decisions made

| Decision | Rationale |
|---|---|
| 7 tasks (within 5-7 range) | A5-1 through A5-5 are contract (types/client/real/mock/tests); A5-6 is module scaffold + manifest; A5-7 is portal pages + event docs |
| Mock fixture IDs use spec §9.4 NPI `8084009009` | Luhn-valid; consistent with SP-2 fixtures per spec note |
| 6 new portal pages (not replacements) | Existing investigations pages are Plan B work; Plan A5 only creates pages for routes that don't exist |
| `getInvestigation` cache policy: `ttl_seconds: 0, backend_down: "fail-closed"` | PHI endpoint — no caching, fail closed per spec §8 |
| 13 read-only cache policies; 5 write operations no cache entry | Per spec §8: write operations fail closed |
| Port 8007 for reclaimrx backend health check | Inferred from `.env.local` pattern; plan-writer note: verify at execution |

## Files produced

- `docs/superpowers/plans/2026-05-18-sp3-plan-a5-contract-frontend.md` — full plan (7 tasks)
- `waves/B10/sub-sessions/sp3-plan-a5.md` — this file

---

STATUS: PASS
REASON: 7-task plan written against confirmed ground-truth paths from audit + direct file reads; no invented paths; verbatim pattern from prescriber-directory impl; all spec §11.5 event contracts instantiated; surgical-changes rule applied to existing portal pages.
ATTEMPTED: Wrote SP-3 Plan A5 covering contract layer (4 files in `src/impls/reclaimrx/`), module scaffold (`packages/modules/reclaimrx/`), manifest update, 6 empty-state portal pages, and 2 event contract docs with complete test specs.
RECOMMENDATION: Dispatch codex consult on plan file `docs/superpowers/plans/2026-05-18-sp3-plan-a5-contract-frontend.md` before execution. Key codex focus areas: (1) verify all 18 endpoint method signatures match spec §5.5 exactly; (2) confirm Zod DecimalStringSchema regex covers all backend Decimal outputs; (3) verify manifest.json additions don't break existing build-manifest validation; (4) confirm portal page shadcn/ui imports (`@/components/ui/card`, `@/components/ui/button`) are available in `portal/operator`.
