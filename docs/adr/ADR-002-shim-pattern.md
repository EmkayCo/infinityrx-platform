# ADR-002: The `_shim/` pattern for pre-integration modules

**Status:** Accepted (transitional — will be retired at Phase 2 close)
**Date:** 2026-04-13
**Deciders:** Platform architecture

## Context

The emergency audit found several modules — billing, payment-processing,
reclaimrx, core-platform — each carrying a `_shim/` directory with
stand-in definitions for things that logically belong in `shared/`:
- `shared.auth.dependencies` (core-platform has `src/_shim/auth.py`)
- `shared.db.session` (billing / payment-processing / reclaimrx each
  define their own sync session factory)
- `shared.events.publisher` (billing has its own `EventBus` Protocol)

These shims exist because modules started building before `shared/`
was complete. Every shim file documents its intent to be deleted at
integration time.

The question is: what guardrails prevent the shims from becoming
permanent?

## Decision

- `_shim/` is a legitimate transitional pattern. A builder is allowed
  to create one when their module's dependency from `shared/` is not
  yet landed.
- Every file under `_shim/` MUST contain a top-of-file integration
  note: what it stands in for, and the exact `from shared.X import Y`
  call site it will be replaced by.
- When the shared primitive lands, the shim is deleted in the same PR
  that replaces its consumers — never in a subsequent cleanup PR.
- Any function in a shim that talks to shared platform state (e.g.,
  the tenant contextvar) MUST delegate to the shared implementation
  rather than maintain its own state. Otherwise the module's view of
  the platform drifts out of sync with everything else. LESSON from
  P1 Item 4: reclaimrx's `_shim/db.py` defined its own
  `_current_tenant` ContextVar disconnected from
  `shared.db.tenant_context.current_tenant_id`, and middleware that
  set the shared var was invisible to reclaimrx code — a silent
  tenant-isolation gap.
- `_shim/` is not a general-purpose hiding place for module-local
  code. Module-local code lives in `src/utils/`, `src/services/`,
  etc. `_shim/` is specifically the name for "this is shared, I just
  haven't been able to import from shared yet."

## Alternatives considered

1. **Ban `_shim/` entirely, require shared to land first.** Rejected:
   creates a hard sequencing dependency. Module builders would block
   on the shared team and the platform ships slower.
2. **Name the directory `_compat/` or `_internal/`.** Rejected:
   `_shim/` is already the term used in every existing file's
   integration note. Changing it is churn with no benefit.

## Consequences

- Audit tool: grep for `_shim/` occurrences — any file older than the
  merged shared primitive it references is an overdue cleanup.
- QA-Security-PHI sweep (agent) should fail the build on any `_shim`
  file whose shared replacement has landed but has not been wired.
- Lessons: the ADR is written because builders will be tempted to
  leave shims in place after the corresponding shared primitive has
  landed; documenting the rule makes the cleanup debt visible.
