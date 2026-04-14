# Tenant Isolation Rules

## Database Queries
- MUST include `tenant_id` in EVERY database query WHERE clause — enforced via `TenantScopedMixin` + `install_tenant_loader`.
- MUST inherit `TenantScopedMixin` on EVERY tenant-owned model — no exceptions.
- MUST call `install_tenant_loader` on EVERY session factory — no module-local session factories that skip it.
- MUST NOT create module-specific `_current_tenant` contextvars — use `shared.db.tenant_context.current_tenant_id` only.
- MUST have PostgreSQL RLS policies as defense-in-depth on every tenant-owned table.

## Redis
- MUST prefix ALL Redis keys with `tenant:{tenant_id}:` — no tenant-unscoped keys.
- Example: `mfa:challenge:{tenant_id}:{token}`, not `mfa:challenge:{token}`.

## Events
- MUST include `tenant_id` in every `EventEnvelope`.
- MUST filter by `tenant_id` in every event consumer.

## API
- MUST validate `x-tenant-id` header as UUID — never accept raw unvalidated string.
- MUST return 403 if authenticated user's `tenant_id` does not match request `tenant_id`.

## Testing
- MUST have automated cross-tenant isolation test for EVERY API endpoint — create 2 tenants, populate both, query as Tenant A, verify zero Tenant B data.
