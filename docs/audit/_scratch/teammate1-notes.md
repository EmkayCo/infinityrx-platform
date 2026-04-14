# Teammate 1 "security-wiring" — Session Notes

**Date:** 2026-04-14
**Branch:** main (worktree agent-aff65db9)

## Baseline
- `uv run pytest modules/core-platform/tests` → 398 passed (worktree root)
- Pre-existing state: AuditMiddleware and TenantIsolationMiddleware defined but NOT in create_app()
- edi-compliance: silent no-op middleware via try/except importing from wrong path
- billing/reclaimrx/reporting/payment-processing: no create_app() factory
- medical-claims/prescriber-directory/edi-compliance: no JWT auth on routes

## Key Discovery
- `AuditMiddleware` in core-platform/src/audit/middleware.py requires `session_factory`, `user_resolver`, `event_bus` — these must be wired carefully
- `TenantIsolationMiddleware` in core-platform/src/infrastructure/tenant_middleware.py requires `resolver: AuthResolver`
- Billing/drug-database/prescriber-directory use sync psycopg2 sessions with hardcoded localhost URLs
- prescriber-directory has no tenant_id on Prescriber model — treating as global NPPES reference table (no TenantScopedMixin warranted per domain), per architectural decision below

## Architectural Decision: prescriber-directory
Prescriber (NPI) is a global reference table (NPPES registry). The `Prescriber` model should NOT have tenant_id. However, satellite tables (CredentialAlert, network assignments) MUST be tenant-scoped. This is consistent with how drug-database handles NDC data as a global reference. The prescriber-directory module has no session-level tenant isolation needed for read-only reference lookups. Document in docs/architecture/tenant_isolation_policy.md.

## Surprises
1. `AuditMiddleware` requires 3 args (session_factory, user_resolver, event_bus) — need shims for modules that don't have full auth wiring
2. edi-compliance DLQ router `build_dlq_router()` is called with no args in the existing code — needs checking
3. The shared `CircuitBreaker` is sync-only — RedisChallengeStore is async — will need an async CircuitBreaker or adaptation

## Work Log
- GROUP 1: mount AuditMiddleware + TenantIsolationMiddleware in core-platform create_app
- GROUP 2: create shared/middleware, remove duplicates
- GROUP 3: create create_app() factories for billing/reclaimrx/reporting/payment-processing
- GROUP 4: fix edi-compliance silent no-op
- GROUP 5: verify all module create_app() factories
- GROUP 6: add JWT auth to unprotected modules
- GROUP 7: prescriber-directory tenant isolation decision
- GROUP 8: config hardening
- GROUP 9: statement_timeout
- GROUP 10: slow query logger
- GROUP 11: Redis circuit breaker
- GROUP 12: audit chain verification job
