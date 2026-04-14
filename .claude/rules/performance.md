# Performance Rules

## Database
- MUST add index on `(tenant_id, {foreign_key})` for every tenant-scoped table with a foreign key.
- MUST add index on `(tenant_id, status)` for every table with a `status` column used in queries.
- MUST use async SQLAlchemy engine — never sync `psycopg2` in API routes.
- MUST NOT have N+1 queries — use `selectinload`/`joinedload` for related objects.

## Caching
- MUST Redis-cache all reference data lookups (NDC, NPI, eligibility) with configurable TTL.
- MUST invalidate cache on data change events.

## Queries
- MUST log queries taking >1 second at WARNING level.
- MUST have `statement_timeout` configured to prevent runaway queries.

## Testing
- MUST have query counter test fixture for N+1 detection in integration tests.
