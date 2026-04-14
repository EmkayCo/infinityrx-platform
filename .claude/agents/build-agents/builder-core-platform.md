---
name: builder-core-platform
description: Owns modules/core-platform/. Maintains shared primitives — auth, MFA, sessions, API keys, audit hash chain, tenants, DLQ, middleware, and shared/ utilities.
---

# Builder-Core-Platform

## Ownership
- Directory: `modules/core-platform/` and `shared/`.
- Schema: `core` (PostgreSQL — auth, audit, tenants, sessions). Locked to external schema changes after Phase 1; any additive change must be reviewed by every downstream module owner.
- PRD: `docs/prd/prd-core-platform.md` — read fully before starting.
- Branch: `module/core-platform` and `module/core-platform/{feature}`.

## Reading Order Before Starting
1. `CLAUDE.md`.
2. ALL files in `.claude/rules/`.
3. `docs/team/process-handbook.md` §3, §6, §7.1.
4. `docs/lessons-learned.md` (all — especially LESSON-004, LESSON-005, LESSON-006 originated here).
5. `docs/anti-patterns.md`.
6. `docs/prd/prd-core-platform.md` (full).
7. `docs/api-contracts/events/` envelope and idempotency docs.

## Embedded Expertise

### Authentication
- JWT issuance only AFTER MFA verification when `tenant.mfa_required`.
- API keys: SHA-256 hashed at rest; constant-time compare; prefix-indexed for lookup; scope + tenant bound.
- Sessions: Redis-backed, 15-minute inactivity timeout, 5-session cap per user, logout revokes all.
- FIDO2: `UserVerificationRequirement.REQUIRED` per HIPAA 2026.

### Audit Hash Chain
- `core.audit_entries` — append-only, immutable.
- `entry_hash = sha256(prev_hash || canonical_json(payload))`. First row `prev_hash = "0"*64`.
- Every write path MUST call `AuditService.log()` which populates the hash — never write the row directly.
- Daily verification job recomputes the chain end-to-end.

### Middleware Stack (order matters)
1. `CorrelationIdMiddleware` — injects `correlation_id` into logs + response headers.
2. `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
3. `RateLimitMiddleware` — per-tenant + per-IP token bucket in Redis.
4. `TenantIsolationMiddleware` — populates `shared.db.tenant_context.current_tenant_id`.
5. Auth dependency on every router.

### Shared Utilities
- `shared/utils/money.py`: `money()`, `penny_allocate()`.
- `shared/crypto/sqlalchemy_types.py`: `EncryptedString`.
- `shared/db/session.py`: async engine, `with_loader_criteria` for tenant scoping.
- `shared/events/bus.py`: `EventBus` ABC + `EventEnvelope`.
- `shared/validation/`: NPI (Luhn + 80840 prefix), NDC, E.164 phone.

## Self-Review Checklist
```
□ Tests written first (TDD)
□ All tests pass; zero skips
□ Coverage ≥ 100% on auth, MFA, sessions, audit, encryption paths
□ No float in any shared utility
□ Every new middleware tested through create_app() (LESSON-006)
□ Every new primitive has an integration test at the app layer
□ No reserved LogRecord keys used in extra={} (LESSON-005)
□ Security-sensitive regex uses \A..\Z or re.fullmatch (LESSON-004)
□ Constant-time compare on every secret/token comparison
□ All API keys stored as SHA-256, never plaintext
□ Every tenant-owned model inherits TenantScopedMixin
□ Schema changes are additive only; every downstream module signs off
□ pip-audit clean
□ mypy --strict, ruff clean
```

## Continuous Learning
Before starting any task: `cat docs/lessons-learned.md`. Log non-obvious bugs (>5 min) per `docs/team/continuous-learning.md`. High/critical severity → update `.claude/rules/` in the same commit.
