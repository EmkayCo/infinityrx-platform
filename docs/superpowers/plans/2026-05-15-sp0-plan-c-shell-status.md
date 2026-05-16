# SP-0 Plan C-shell — Acceptance Status

**Status:** EXECUTION COMPLETE — pending codex pass-1
**Branch:** wave/B10-w5-plan-c-shell-exec
**Date:** 2026-05-15

## Ships list
- `packages/shell`: scaffolded, builds, typechecks, lints, tests green
- `<RequireAuth>` + `<RequireRole>`: RSC auth gates, 11 tests
- `getSessionUser`: UserIdentity extractor, 4 tests
- `AppShellMount` + `ModuleNav`: role-filtered, manifest-ordered nav, 10 tests
- QA mode toggle: `parseQaMode`, `buildQaModeCookieValue`, `applyQaModeMiddleware`, 11 tests
- `wrapFetch`: ClientConfig.fetch instrumentation hook, 13 tests; production no-op guard + bounded recursive PHI key redaction (depth 6, cycle detection) + 4KB body cap
- `inspector-store` + `InspectorPanel`: nanostores atom + slide-out panel, 3 tests
- `/qa-harness/*` pages: 5 route page components (health, composition, mock, factory, correlation), 6 tests
- `framework-bound.test.ts`: 5 tests asserting SD-2 mandate
- `portal/operator/middleware.ts`: shell middleware wired (QA mode cookie propagation)
- `portal/operator/app/(authenticated)/layout.tsx`: RequireAuth + AppShellMount gate

## Deferred scope (not in Plan C-shell)
- Full CommandPalette Cmd+K keyboard wiring — Plan D (module registration)
- Module nav entry registration by module packages — Plan D
- Tailwind design tokens in portal — Plan D
- Real `_generated/manifest.json` content — Plan D codegen
- Python backend auth refactor — separate wave

## Test count
63 tests (packages/shell only; does not include Plan B/C tests)

## Decision log
- `wrapFetch` wraps `ClientConfig.fetch` at injection time rather than patching globalThis.fetch — safe for concurrent requests
- Root layout (`portal/operator/app/layout.tsx`) is UNGATED — `RequireAuth` lives exclusively in `(authenticated)/layout.tsx` to prevent /login infinite redirect loop (BLOCK-3 fix)
- Login page at `(auth)/login` (existing) is outside `(authenticated)/` — public route group confirmed safe
- `InspectorPanelProps = Record<string, never>` (type alias, not empty interface) — avoids `@typescript-eslint/no-empty-object-type` lint error
- Option A auth architecture: next-auth `callbacks.jwt` calls `verifyAccessToken` from `@infinityrx/auth` at login time; per-request revocation deferred to future wave
